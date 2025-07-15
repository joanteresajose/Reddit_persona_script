#!/usr/bin/env python3
"""
Reddit User Persona Extractor

A Python script that analyzes Reddit user profiles to create detailed personas
based on their posts and comments using AI analysis.

Usage:
    python reddit_persona_extractor.py <reddit_profile_url>

Example:
    python reddit_persona_extractor.py https://www.reddit.com/user/kojied/
"""

import praw
import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from emergentintegrations.llm.chat import LlmChat, UserMessage
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RedditPersonaExtractor:
    def __init__(self):
        """Initialize the Reddit Persona Extractor with API credentials."""
        # Reddit API credentials
        self.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
        self.reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.reddit_username = os.getenv('REDDIT_USERNAME')
        
        # Gemini API credentials
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # Validate credentials
        if not all([self.reddit_client_id, self.reddit_client_secret, self.reddit_username]):
            raise ValueError("Missing Reddit API credentials. Please check your .env file.")
        
        if not self.gemini_api_key:
            raise ValueError("Missing Gemini API key. Please check your .env file.")
        
        # Initialize Reddit API
        self.reddit = praw.Reddit(
            client_id=self.reddit_client_id,
            client_secret=self.reddit_client_secret,
            user_agent=f'PersonaExtractor:1.0 (by /u/{self.reddit_username})'
        )
        
        print(f"✅ Reddit API initialized successfully")
        print(f"✅ Gemini API key configured")
    
    def extract_username(self, reddit_url: str) -> str:
        """Extract username from Reddit URL."""
        parsed = urlparse(reddit_url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'user':
            return path_parts[1]
        raise ValueError("Invalid Reddit user URL format. Expected: https://www.reddit.com/user/username/")
    
    def scrape_reddit_profile(self, reddit_url: str) -> dict:
        """Scrape Reddit profile posts and comments using PRAW."""
        username = self.extract_username(reddit_url)
        print(f"🔍 Scraping profile for user: {username}")
        
        try:
            # Get the redditor
            redditor = self.reddit.redditor(username)
            
            # Test if user exists
            try:
                redditor.id
                print(f"✅ User {username} found")
            except Exception:
                raise ValueError(f"Reddit user '{username}' not found or is suspended")
            
            posts = []
            comments = []
            
            # Scrape posts (submissions)
            print("📄 Scraping posts...")
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
                print(f"✅ Scraped {len(posts)} posts")
            except Exception as e:
                print(f"⚠️ Error scraping posts: {e}")

            # Scrape comments
            print("💬 Scraping comments...")
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
                print(f"✅ Scraped {len(comments)} comments")
            except Exception as e:
                print(f"⚠️ Error scraping comments: {e}")

            total_content = len(posts) + len(comments)
            if total_content == 0:
                raise ValueError(f"No posts or comments found for user {username}")
            
            print(f"📊 Total content scraped: {len(posts)} posts + {len(comments)} comments = {total_content} items")
            
            return {
                'username': username,
                'posts': posts,
                'comments': comments,
                'total_posts': len(posts),
                'total_comments': len(comments)
            }
            
        except Exception as e:
            raise ValueError(f"Error scraping Reddit profile: {str(e)}")
    
    def prepare_content_for_analysis(self, scraped_data: dict) -> str:
        """Prepare scraped content for LLM analysis."""
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
    
    async def analyze_persona(self, scraped_data: dict) -> dict:
        """Analyze scraped Reddit data to create user persona using Gemini."""
        print("🤖 Analyzing persona with Gemini AI...")
        
        # Prepare content for analysis
        content_text = self.prepare_content_for_analysis(scraped_data)
        
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
        
        print("✅ Persona analysis completed")
        
        # Parse the response
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                persona_json = json.loads(json_str)
            else:
                raise ValueError("Could not parse JSON from response")
                
            return persona_json
        except Exception as e:
            print(f"⚠️ Error parsing persona response: {e}")
            return {'error': 'Failed to parse persona', 'raw_response': response}
    
    def create_citations(self, persona_data: dict, scraped_data: dict) -> dict:
        """Create citations linking persona traits to source content."""
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
    
    def generate_persona_file(self, username: str, persona: dict, citations: dict) -> str:
        """Generate persona text file with citations."""
        
        # Create output directory if it doesn't exist
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        file_path = output_dir / f"{username}_persona.txt"
        
        content = f"""
REDDIT USER PERSONA ANALYSIS
Username: {username}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Generated by: Reddit User Persona Extractor
URL: https://www.reddit.com/user/{username}/

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
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
    
    async def extract_persona(self, reddit_url: str) -> str:
        """Main method to extract persona from Reddit URL."""
        try:
            # Step 1: Scrape Reddit profile
            scraped_data = self.scrape_reddit_profile(reddit_url)
            
            # Step 2: Analyze persona with AI
            persona_data = await self.analyze_persona(scraped_data)
            
            # Step 3: Create citations
            citations = self.create_citations(persona_data, scraped_data)
            
            # Step 4: Generate persona file
            file_path = self.generate_persona_file(scraped_data['username'], persona_data, citations)
            
            print(f"✅ Persona analysis completed successfully!")
            print(f"📄 Output file: {file_path}")
            
            return file_path
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return None


def main():
    """Main function to run the Reddit Persona Extractor."""
    parser = argparse.ArgumentParser(
        description="Extract user personas from Reddit profiles using AI analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python reddit_persona_extractor.py https://www.reddit.com/user/kojied/
    python reddit_persona_extractor.py https://www.reddit.com/user/Hungry-Move-6603/

Note: Make sure to configure your API credentials in the .env file before running.
        """
    )
    parser.add_argument('reddit_url', help='Reddit profile URL (e.g., https://www.reddit.com/user/username/)')
    parser.add_argument('--output', '-o', help='Output directory (default: ./output/)')
    
    args = parser.parse_args()
    
    # Validate URL format
    if not args.reddit_url.startswith('https://www.reddit.com/user/'):
        print("❌ Error: Invalid Reddit URL format")
        print("Expected format: https://www.reddit.com/user/username/")
        sys.exit(1)
    
    print("🚀 Reddit User Persona Extractor")
    print("="*50)
    print(f"Target URL: {args.reddit_url}")
    print()
    
    try:
        # Initialize extractor
        extractor = RedditPersonaExtractor()
        
        # Extract persona
        result = asyncio.run(extractor.extract_persona(args.reddit_url))
        
        if result:
            print(f"\n🎉 Success! Persona file generated: {result}")
            print("\nNext steps:")
            print("1. Open the generated .txt file to view the complete persona analysis")
            print("2. Review the citations to see which posts/comments support each trait")
            print("3. Use the insights for your research, marketing, or analysis needs")
        else:
            print("\n❌ Failed to generate persona analysis")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Critical error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check your .env file contains all required API credentials")
        print("2. Verify the Reddit profile URL is correct and accessible")
        print("3. Ensure you have internet connectivity")
        sys.exit(1)


if __name__ == "__main__":
    main()
