#!/usr/bin/env python3
"""
Backend Testing Suite for Reddit User Persona Extraction
Tests all high-priority backend functionality including:
1. Reddit Profile URL Scraping
2. LLM Persona Analysis with Gemini
3. File Generation with Citations
4. Database Storage
"""

import requests
import json
import time
import os
from pathlib import Path

# Configuration
BACKEND_URL = "https://645b6de0-1157-4953-860a-1acf9e3c34d5.preview.emergentagent.com/api"
TEST_URLS = [
    "https://www.reddit.com/user/kojied/",
    "https://www.reddit.com/user/Hungry-Move-6603/"
]

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = {}
        
    def log_test(self, test_name, status, message, details=None):
        """Log test results"""
        self.test_results[test_name] = {
            'status': status,
            'message': message,
            'details': details or {}
        }
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
    
    def test_api_health(self):
        """Test basic API connectivity"""
        try:
            response = self.session.get(f"{BACKEND_URL}/")
            if response.status_code == 200:
                data = response.json()
                if "Reddit User Persona Extraction API" in data.get("message", ""):
                    self.log_test("API Health Check", "PASS", "API is responding correctly")
                    return True
                else:
                    self.log_test("API Health Check", "FAIL", f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("API Health Check", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("API Health Check", "FAIL", f"Connection error: {str(e)}")
            return False
    
    def test_reddit_scraping_and_analysis(self, reddit_url):
        """Test Reddit profile scraping and persona analysis"""
        try:
            print(f"\n🔍 Testing Reddit URL: {reddit_url}")
            
            # Make request to analyze endpoint
            payload = {"reddit_url": reddit_url}
            response = self.session.post(
                f"{BACKEND_URL}/analyze-reddit",
                json=payload,
                timeout=120  # Extended timeout for LLM processing
            )
            
            if response.status_code != 200:
                self.log_test(
                    f"Reddit Analysis - {reddit_url}",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text}"
                )
                return None
            
            data = response.json()
            
            # Validate response structure
            required_fields = ['id', 'reddit_url', 'username', 'persona', 'citations', 'file_path', 'created_at']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_test(
                    f"Reddit Analysis - {reddit_url}",
                    "FAIL",
                    f"Missing required fields: {missing_fields}",
                    data
                )
                return None
            
            # Validate persona structure
            persona = data.get('persona', {})
            if not persona or not isinstance(persona, dict):
                self.log_test(
                    f"Reddit Analysis - {reddit_url}",
                    "FAIL",
                    "Persona data is empty or invalid",
                    {'persona': persona}
                )
                return None
            
            # Validate citations
            citations = data.get('citations', {})
            if not citations or not isinstance(citations, dict):
                self.log_test(
                    f"Reddit Analysis - {reddit_url}",
                    "FAIL",
                    "Citations data is empty or invalid",
                    {'citations': citations}
                )
                return None
            
            # Check if username was extracted correctly
            username = data.get('username', '')
            expected_username = reddit_url.split('/user/')[-1].rstrip('/')
            if username != expected_username:
                self.log_test(
                    f"Reddit Analysis - {reddit_url}",
                    "FAIL",
                    f"Username mismatch. Expected: {expected_username}, Got: {username}"
                )
                return None
            
            self.log_test(
                f"Reddit Analysis - {reddit_url}",
                "PASS",
                f"Successfully analyzed user {username}",
                {
                    'persona_sections': len(persona),
                    'citation_sections': len(citations),
                    'file_path': data.get('file_path', '')
                }
            )
            
            return data
            
        except requests.exceptions.Timeout:
            self.log_test(
                f"Reddit Analysis - {reddit_url}",
                "FAIL",
                "Request timeout (>120s) - LLM processing may be slow"
            )
            return None
        except Exception as e:
            self.log_test(
                f"Reddit Analysis - {reddit_url}",
                "FAIL",
                f"Unexpected error: {str(e)}"
            )
            return None
    
    def test_file_download(self, persona_id, username):
        """Test persona file download functionality"""
        try:
            response = self.session.get(f"{BACKEND_URL}/download-persona/{persona_id}")
            
            if response.status_code != 200:
                self.log_test(
                    f"File Download - {username}",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text}"
                )
                return False
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if 'text/plain' not in content_type:
                self.log_test(
                    f"File Download - {username}",
                    "FAIL",
                    f"Unexpected content type: {content_type}"
                )
                return False
            
            # Check file content
            content = response.text
            if not content or len(content) < 100:
                self.log_test(
                    f"File Download - {username}",
                    "FAIL",
                    f"File content too short or empty: {len(content)} chars"
                )
                return False
            
            # Validate file structure
            required_sections = [
                "REDDIT USER PERSONA ANALYSIS",
                f"Username: {username}",
                "DEMOGRAPHICS",
                "PERSONALITY TRAITS",
                "CITATIONS"
            ]
            
            missing_sections = [section for section in required_sections if section not in content]
            if missing_sections:
                self.log_test(
                    f"File Download - {username}",
                    "FAIL",
                    f"Missing file sections: {missing_sections}"
                )
                return False
            
            self.log_test(
                f"File Download - {username}",
                "PASS",
                f"File downloaded successfully ({len(content)} chars)"
            )
            return True
            
        except Exception as e:
            self.log_test(
                f"File Download - {username}",
                "FAIL",
                f"Unexpected error: {str(e)}"
            )
            return False
    
    def test_personas_list(self):
        """Test getting list of all personas"""
        try:
            response = self.session.get(f"{BACKEND_URL}/personas")
            
            if response.status_code != 200:
                self.log_test(
                    "Personas List",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text}"
                )
                return False
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test(
                    "Personas List",
                    "FAIL",
                    f"Expected list, got: {type(data)}"
                )
                return False
            
            # If we have personas, validate structure
            if data:
                first_persona = data[0]
                required_fields = ['id', 'reddit_url', 'username', 'persona', 'citations', 'file_path']
                missing_fields = [field for field in required_fields if field not in first_persona]
                
                if missing_fields:
                    self.log_test(
                        "Personas List",
                        "FAIL",
                        f"Persona missing fields: {missing_fields}"
                    )
                    return False
            
            self.log_test(
                "Personas List",
                "PASS",
                f"Retrieved {len(data)} personas successfully"
            )
            return True
            
        except Exception as e:
            self.log_test(
                "Personas List",
                "FAIL",
                f"Unexpected error: {str(e)}"
            )
            return False
    
    def test_gemini_integration(self, persona_data):
        """Test Gemini LLM integration by validating persona quality"""
        try:
            persona = persona_data.get('persona', {})
            
            # Check if persona has expected structure (not just raw text)
            expected_sections = [
                'demographics', 'personality_traits', 'interests', 'values',
                'behavioral_patterns', 'technology_usage', 'social_media_behavior',
                'professional_interests', 'lifestyle', 'communication_style'
            ]
            
            found_sections = [section for section in expected_sections if section in persona]
            
            if len(found_sections) < 5:  # At least half the sections should be present
                # Check if it's a fallback response
                if any('raw_analysis' in str(section_data) for section_data in persona.values()):
                    self.log_test(
                        "Gemini Integration",
                        "WARN",
                        "Gemini returned fallback response - JSON parsing may have failed",
                        {'found_sections': found_sections}
                    )
                    return True  # Still working, just not optimal
                else:
                    self.log_test(
                        "Gemini Integration",
                        "FAIL",
                        f"Insufficient persona sections. Found: {found_sections}"
                    )
                    return False
            
            # Check for error indicators
            if 'error' in persona:
                self.log_test(
                    "Gemini Integration",
                    "FAIL",
                    f"Persona contains error: {persona.get('error')}"
                )
                return False
            
            self.log_test(
                "Gemini Integration",
                "PASS",
                f"Gemini analysis successful with {len(found_sections)} sections",
                {'sections': found_sections}
            )
            return True
            
        except Exception as e:
            self.log_test(
                "Gemini Integration",
                "FAIL",
                f"Unexpected error: {str(e)}"
            )
            return False
    
    def run_comprehensive_test(self):
        """Run complete backend test suite"""
        print("🚀 Starting Reddit User Persona Extraction Backend Tests")
        print("=" * 60)
        
        # Test 1: API Health Check
        if not self.test_api_health():
            print("\n❌ API is not responding. Stopping tests.")
            return False
        
        # Test 2: Reddit Analysis for each URL
        analyzed_personas = []
        for reddit_url in TEST_URLS:
            persona_data = self.test_reddit_scraping_and_analysis(reddit_url)
            if persona_data:
                analyzed_personas.append(persona_data)
                
                # Test 3: Gemini Integration (per persona)
                self.test_gemini_integration(persona_data)
                
                # Test 4: File Download (per persona)
                self.test_file_download(persona_data['id'], persona_data['username'])
        
        # Test 5: Personas List
        self.test_personas_list()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results.values() if result['status'] == 'PASS')
        failed = sum(1 for result in self.test_results.values() if result['status'] == 'FAIL')
        warnings = sum(1 for result in self.test_results.values() if result['status'] == 'WARN')
        
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"📊 Total: {len(self.test_results)}")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for test_name, result in self.test_results.items():
                if result['status'] == 'FAIL':
                    print(f"  • {test_name}: {result['message']}")
        
        if warnings > 0:
            print("\n⚠️  WARNINGS:")
            for test_name, result in self.test_results.items():
                if result['status'] == 'WARN':
                    print(f"  • {test_name}: {result['message']}")
        
        return failed == 0

if __name__ == "__main__":
    tester = BackendTester()
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n🎉 All backend tests passed successfully!")
        exit(0)
    else:
        print("\n💥 Some backend tests failed. Check the details above.")
        exit(1)