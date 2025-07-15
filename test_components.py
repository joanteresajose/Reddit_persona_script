#!/usr/bin/env python3
"""
Test Gemini Integration and File Generation with Mock Data
Since Reddit scraping is blocked, test other components independently
"""

import requests
import json
import asyncio
import sys
import os
sys.path.append('/app/backend')

# Test Gemini integration directly
async def test_gemini_integration():
    """Test Gemini API integration with mock Reddit data"""
    try:
        from server import PersonaAnalyzer
        
        # Mock scraped Reddit data
        mock_data = {
            'username': 'testuser',
            'posts': [
                {
                    'type': 'post',
                    'title': 'Love programming in Python',
                    'selftext': 'Been coding for 5 years, really enjoy backend development',
                    'subreddit': 'programming',
                    'score': 25,
                    'created_utc': 1640995200,
                    'url': 'https://www.reddit.com/r/programming/test1'
                },
                {
                    'type': 'post', 
                    'title': 'Best coffee shops in Seattle',
                    'selftext': 'Looking for good places to work remotely',
                    'subreddit': 'Seattle',
                    'score': 15,
                    'created_utc': 1640995300,
                    'url': 'https://www.reddit.com/r/Seattle/test2'
                }
            ],
            'comments': [
                {
                    'type': 'comment',
                    'body': 'I agree, FastAPI is much better than Flask for modern APIs',
                    'subreddit': 'webdev',
                    'score': 10,
                    'created_utc': 1640995400,
                    'url': 'https://www.reddit.com/r/webdev/test3'
                },
                {
                    'type': 'comment',
                    'body': 'Working from home has been great for productivity',
                    'subreddit': 'remotework',
                    'score': 8,
                    'created_utc': 1640995500,
                    'url': 'https://www.reddit.com/r/remotework/test4'
                }
            ]
        }
        
        analyzer = PersonaAnalyzer()
        result = await analyzer.analyze_persona(mock_data)
        
        print("✅ Gemini Integration Test Results:")
        print(f"   Persona sections: {len(result.get('persona', {}))}")
        print(f"   Citations sections: {len(result.get('citations', {}))}")
        
        # Check if persona has expected structure
        persona = result.get('persona', {})
        if persona and isinstance(persona, dict):
            if 'error' in persona:
                print(f"❌ Gemini returned error: {persona['error']}")
                return False
            else:
                print("✅ Gemini analysis completed successfully")
                return True
        else:
            print("❌ Invalid persona structure returned")
            return False
            
    except Exception as e:
        print(f"❌ Gemini integration test failed: {str(e)}")
        return False

# Test file generation
async def test_file_generation():
    """Test file generation with mock data"""
    try:
        from server import generate_persona_file
        
        mock_persona = {
            'demographics': {'age_range': '25-35', 'location': 'Seattle'},
            'personality_traits': {'openness': 'high', 'conscientiousness': 'medium'},
            'interests': {'programming': 'high', 'coffee': 'medium'}
        }
        
        mock_citations = {
            'demographics': [
                {
                    'type': 'post',
                    'content': 'Best coffee shops in Seattle...',
                    'url': 'https://www.reddit.com/r/Seattle/test',
                    'subreddit': 'Seattle',
                    'score': 15
                }
            ]
        }
        
        file_path = await generate_persona_file('testuser', mock_persona, mock_citations)
        
        # Check if file was created
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            
            if len(content) > 100 and 'testuser' in content:
                print("✅ File generation test passed")
                print(f"   File created: {file_path}")
                print(f"   Content length: {len(content)} chars")
                return True
            else:
                print("❌ File content is invalid")
                return False
        else:
            print("❌ File was not created")
            return False
            
    except Exception as e:
        print(f"❌ File generation test failed: {str(e)}")
        return False

async def main():
    print("🧪 Testing Individual Components with Mock Data")
    print("=" * 50)
    
    gemini_result = await test_gemini_integration()
    file_result = await test_file_generation()
    
    print("\n📊 Component Test Summary:")
    print(f"✅ Gemini Integration: {'PASS' if gemini_result else 'FAIL'}")
    print(f"✅ File Generation: {'PASS' if file_result else 'FAIL'}")
    
    return gemini_result and file_result

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)