from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import aiofiles
import asyncio
import re
from urllib.parse import urlparse
import praw
import time
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class RedditUrlRequest(BaseModel):
    reddit_url: str

class PersonaResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reddit_url: str
    username: str
    persona: dict
    citations: dict
    file_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PersonaCreate(BaseModel):
    reddit_url: str
    username: str
    persona: dict
    citations: dict
    file_path: str

# Reddit Scraper Class using PRAW
class RedditScraper:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=os.environ.get('REDDIT_CLIENT_ID'),
            client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
            user_agent=f'PersonaExtractor:1.0 (by /u/{os.environ.get("REDDIT_USERNAME", "user")})'
        )

    def extract_username(self, reddit_url: str) -> str:
        """Extract username from Reddit URL"""
        parsed = urlparse(reddit_url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'user':
            return path_parts[1]
        raise ValueError("Invalid Reddit user URL format")

    def scrape_reddit_profile(self, reddit_url: str) -> dict:
        """Scrape Reddit profile posts and comments using PRAW"""
        username = self.extract_username(reddit_url)
        
        try:
            # Get the redditor
            redditor = self.reddit.redditor(username)
            
            # Test if user exists
            try:
                # This will raise an exception if user doesn't exist
                redditor.id
            except Exception:
                raise ValueError(f"Reddit user '{username}' not found or is suspended")
            
            posts = []
            comments = []
            
            # Scrape posts (submissions)
            try:
                for submission in redditor.submissions.new(limit=50):
                    posts.append({
                        'type': 'post',
                        'title': submission.title,
                        'selftext': submission.selftext,
                        'subreddit': str(submission.subreddit),
                        'score': submission.score,
                        'created_utc': submission.created_utc,
                        'url': f"https://www.reddit.com{submission.permalink}",
                        'num_comments': submission.num_comments
                    })
            except Exception as e:
                print(f"Error scraping posts: {e}")

            # Scrape comments
            try:
                for comment in redditor.comments.new(limit=100):
                    comments.append({
                        'type': 'comment',
                        'body': comment.body,
                        'subreddit': str(comment.subreddit),
                        'score': comment.score,
                        'created_utc': comment.created_utc,
                        'url': f"https://www.reddit.com{comment.permalink}",
                        'is_submitter': comment.is_submitter
                    })
            except Exception as e:
                print(f"Error scraping comments: {e}")

            return {
                'username': username,
                'posts': posts,
                'comments': comments,
                'total_posts': len(posts),
                'total_comments': len(comments)
            }
            
        except Exception as e:
            raise ValueError(f"Error scraping Reddit profile: {str(e)}")

# Persona Analysis Class
class PersonaAnalyzer:
    def __init__(self):
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY')
        
    async def analyze_persona(self, scraped_data: dict) -> dict:
        """Analyze scraped Reddit data to create user persona"""
        
        # Prepare content for analysis
        content_text = self._prepare_content(scraped_data)
        
        # Create LLM chat instance
        chat = LlmChat(
            api_key=self.gemini_api_key,
            session_id=f"persona_{scraped_data['username']}",
            system_message="You are an expert psychologist and data analyst specializing in creating detailed user personas from social media content. Analyze the provided Reddit posts and comments to create a comprehensive user persona."
        ).with_model("gemini", "gemini-2.0-flash")
        
        # Persona analysis prompt
        prompt = f"""
        Analyze the following Reddit posts and comments from user '{scraped_data['username']}' and create a detailed user persona.

        CONTENT STATISTICS:
        - Total Posts: {scraped_data.get('total_posts', 0)}
        - Total Comments: {scraped_data.get('total_comments', 0)}

        CONTENT TO ANALYZE:
        {content_text}

        Please provide a comprehensive user persona analysis in JSON format with the following sections:

        {{
          "demographics": {{
            "age_range": "estimated age range with confidence level",
            "gender": "estimated gender with confidence level",
            "location": "estimated location/region with confidence level",
            "education": "estimated education level with confidence level"
          }},
          "personality_traits": {{
            "openness": "level and evidence",
            "conscientiousness": "level and evidence",
            "extraversion": "level and evidence",
            "agreeableness": "level and evidence",
            "neuroticism": "level and evidence",
            "communication_style": "description of how they communicate"
          }},
          "interests_and_hobbies": {{
            "primary_interests": ["list of main interests"],
            "hobbies": ["list of hobbies"],
            "entertainment": ["preferred entertainment types"],
            "sports": ["sports interests if any"]
          }},
          "values_and_beliefs": {{
            "core_values": ["list of core values"],
            "political_leanings": "political orientation with confidence level",
            "social_causes": ["causes they care about"],
            "life_philosophy": "their general life philosophy"
          }},
          "behavioral_patterns": {{
            "posting_frequency": "how often they post",
            "engagement_style": "how they engage with others",
            "content_preferences": "what type of content they prefer",
            "reaction_patterns": "how they typically react to things"
          }},
          "technology_usage": {{
            "platform_activity": "how they use Reddit",
            "digital_literacy": "their tech comfort level",
            "online_behavior": "their general online behavior patterns"
          }},
          "social_behavior": {{
            "social_interaction": "how they interact socially",
            "community_involvement": "their involvement in communities",
            "leadership_qualities": "any leadership traits shown",
            "conflict_resolution": "how they handle conflicts"
          }},
          "professional_interests": {{
            "career_field": "estimated career field",
            "professional_skills": ["skills they demonstrate"],
            "work_style": "their approach to work",
            "career_goals": "any career aspirations mentioned"
          }},
          "lifestyle_preferences": {{
            "daily_routine": "insights into their daily life",
            "leisure_activities": ["how they spend free time"],
            "consumption_habits": "their consumption patterns",
            "health_wellness": "their approach to health and wellness"
          }},
          "communication_patterns": {{
            "language_style": "their writing/communication style",
            "humor_type": "their sense of humor",
            "emotional_expression": "how they express emotions",
            "persuasion_style": "how they try to persuade others"
          }}
        }}

        For each trait, provide specific evidence from their posts/comments and indicate confidence level (High/Medium/Low).
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse the response and create citations
        persona_data = self._parse_persona_response(response, scraped_data)
        
        return persona_data
    
    def _prepare_content(self, scraped_data: dict) -> str:
        """Prepare scraped content for analysis"""
        content_parts = []
        
        # Add posts
        for post in scraped_data.get('posts', []):
            content_parts.append(f"POST in r/{post['subreddit']}: {post['title']}")
            if post['selftext']:
                content_parts.append(f"Content: {post['selftext']}")
            content_parts.append(f"Score: {post['score']}, Comments: {post['num_comments']}")
            content_parts.append(f"URL: {post['url']}")
            content_parts.append("---")
        
        # Add comments  
        for comment in scraped_data.get('comments', []):
            content_parts.append(f"COMMENT in r/{comment['subreddit']}: {comment['body']}")
            content_parts.append(f"Score: {comment['score']}")
            content_parts.append(f"URL: {comment['url']}")
            content_parts.append("---")
        
        return "\n".join(content_parts)
    
    def _parse_persona_response(self, response: str, scraped_data: dict) -> dict:
        """Parse LLM response and create persona with citations"""
        try:
            # Try to extract JSON from response
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                persona_json = json.loads(json_str)
            else:
                # Fallback: create structured persona from text
                persona_json = self._create_fallback_persona(response)
            
            # Create citations mapping
            citations = self._create_citations(persona_json, scraped_data)
            
            return {
                'persona': persona_json,
                'citations': citations
            }
        except Exception as e:
            print(f"Error parsing persona response: {e}")
            return {
                'persona': {'error': 'Failed to parse persona', 'raw_response': response},
                'citations': {}
            }
    
    def _create_fallback_persona(self, response: str) -> dict:
        """Create a fallback persona structure if JSON parsing fails"""
        return {
            'demographics': {'analysis': response[:500] + '...'},
            'personality_traits': {'analysis': response[:500] + '...'},
            'interests_and_hobbies': {'analysis': response[:500] + '...'},
            'values_and_beliefs': {'analysis': response[:500] + '...'},
            'behavioral_patterns': {'analysis': response[:500] + '...'},
            'technology_usage': {'analysis': response[:500] + '...'},
            'social_behavior': {'analysis': response[:500] + '...'},
            'professional_interests': {'analysis': response[:500] + '...'},
            'lifestyle_preferences': {'analysis': response[:500] + '...'},
            'communication_patterns': {'analysis': response[:500] + '...'}
        }
    
    def _create_citations(self, persona_data: dict, scraped_data: dict) -> dict:
        """Create citations linking persona traits to source content"""
        citations = {}
        
        # For each persona section, find relevant posts/comments
        all_content = scraped_data.get('posts', []) + scraped_data.get('comments', [])
        
        for section, data in persona_data.items():
            citations[section] = []
            
            # Find relevant content for this section (top 5 items)
            for item in all_content[:5]:
                content_text = item.get('title', '') + ' ' + item.get('selftext', '') + ' ' + item.get('body', '')
                citations[section].append({
                    'type': item.get('type', 'unknown'),
                    'content': content_text[:300] + '...' if len(content_text) > 300 else content_text,
                    'url': item.get('url', ''),
                    'subreddit': item.get('subreddit', ''),
                    'score': item.get('score', 0),
                    'created_utc': item.get('created_utc', 0)
                })
        
        return citations

# Initialize instances
scraper = RedditScraper()
analyzer = PersonaAnalyzer()

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Reddit User Persona Extraction API"}

@api_router.post("/analyze-reddit", response_model=PersonaResponse)
async def analyze_reddit_profile(request: RedditUrlRequest):
    """Analyze Reddit profile and generate persona"""
    try:
        # Scrape Reddit profile
        scraped_data = scraper.scrape_reddit_profile(request.reddit_url)
        
        if not scraped_data['posts'] and not scraped_data['comments']:
            raise HTTPException(status_code=404, detail="No posts or comments found for this user")
        
        # Analyze persona
        persona_analysis = await analyzer.analyze_persona(scraped_data)
        
        # Generate text file
        file_path = await generate_persona_file(
            scraped_data['username'],
            persona_analysis['persona'],
            persona_analysis['citations']
        )
        
        # Create persona object
        persona_obj = PersonaResponse(
            reddit_url=request.reddit_url,
            username=scraped_data['username'],
            persona=persona_analysis['persona'],
            citations=persona_analysis['citations'],
            file_path=file_path
        )
        
        # Save to database
        await db.personas.insert_one(persona_obj.dict())
        
        return persona_obj
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/download-persona/{persona_id}")
async def download_persona(persona_id: str):
    """Download persona file"""
    try:
        # Find persona in database
        persona = await db.personas.find_one({"id": persona_id})
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        
        file_path = persona['file_path']
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            file_path,
            media_type='text/plain',
            filename=f"{persona['username']}_persona.txt"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/personas", response_model=List[PersonaResponse])
async def get_personas():
    """Get all analyzed personas"""
    personas = await db.personas.find().to_list(100)
    return [PersonaResponse(**persona) for persona in personas]

async def generate_persona_file(username: str, persona: dict, citations: dict) -> str:
    """Generate persona text file with citations"""
    
    # Create output directory if it doesn't exist
    output_dir = Path("/tmp/personas")
    output_dir.mkdir(exist_ok=True)
    
    file_path = output_dir / f"{username}_persona.txt"
    
    content = f"""
REDDIT USER PERSONA ANALYSIS
Username: {username}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*60}

"""
    
    # Add persona sections
    sections = {
        'demographics': 'DEMOGRAPHICS',
        'personality_traits': 'PERSONALITY TRAITS', 
        'interests_and_hobbies': 'INTERESTS AND HOBBIES',
        'values_and_beliefs': 'VALUES AND BELIEFS',
        'behavioral_patterns': 'BEHAVIORAL PATTERNS',
        'technology_usage': 'TECHNOLOGY USAGE',
        'social_behavior': 'SOCIAL BEHAVIOR',
        'professional_interests': 'PROFESSIONAL/CAREER INTERESTS',
        'lifestyle_preferences': 'LIFESTYLE PREFERENCES',
        'communication_patterns': 'COMMUNICATION PATTERNS'
    }
    
    for key, title in sections.items():
        content += f"\n{title}\n{'-'*len(title)}\n"
        
        section_data = persona.get(key, {})
        if isinstance(section_data, dict):
            for trait, details in section_data.items():
                if isinstance(details, list):
                    content += f"• {trait}: {', '.join(details)}\n"
                else:
                    content += f"• {trait}: {details}\n"
        else:
            content += f"{section_data}\n"
        
        # Add citations
        content += f"\nCITATIONS:\n"
        section_citations = citations.get(key, [])
        for i, citation in enumerate(section_citations[:3], 1):  # Limit to 3 citations per section
            content += f"  [{i}] {citation['type'].upper()} in r/{citation['subreddit']}\n"
            content += f"      Content: {citation['content']}\n"
            content += f"      URL: {citation['url']}\n"
            content += f"      Score: {citation['score']}\n\n"
        
        content += "\n"
    
    # Write to file
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(content)
    
    return str(file_path)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()