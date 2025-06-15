# SPDX-FileCopyrightText: Copyright (c) 2025 YOUR_NAME. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import aiohttp
import json
import carb
from typing import Dict, List, Optional, Any
import base64
import os

class LLMInterface:
    """Advanced LLM Interface supporting multiple providers including OpenRouter"""
    
    def __init__(self):
        self.session = None
        self.provider = None
        self.api_key = None
        self.model = None
        self.base_url = None
        self.headers = {}
        
        # Provider configurations
        self.providers = {
            "openai": {
                "base_url": "https://api.openai.com/v1/chat/completions",
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o"],
                "default_model": "gpt-4"
            },
            "anthropic": {
                "base_url": "https://api.anthropic.com/v1/messages",
                "models": ["claude-3-sonnet", "claude-3-opus", "claude-3-haiku"],
                "default_model": "claude-3-sonnet"
            },
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1/chat/completions",
                "models": [
                    "meta-llama/llama-3.1-8b-instruct:free",
                    "meta-llama/llama-3.1-70b-instruct",
                    "anthropic/claude-3.5-sonnet",
                    "openai/gpt-4o",
                    "google/gemini-pro-1.5",
                    "mistralai/mixtral-8x7b-instruct",
                    "cohere/command-r-plus"
                ],
                "default_model": "meta-llama/llama-3.1-8b-instruct:free"
            },
            "ollama": {
                "base_url": "http://localhost:11434/api/chat",
                "models": ["llama2", "codellama", "mistral", "neural-chat"],
                "default_model": "llama2"
            }
        }
    
    async def initialize(self, provider: str, api_key: str, model: str = None):
        """Initialize LLM connection"""
        try:
            if provider not in self.providers:
                raise ValueError(f"Unsupported provider: {provider}")
            
            self.provider = provider
            self.api_key = api_key
            self.model = model or self.providers[provider]["default_model"]
            self.base_url = self.providers[provider]["base_url"]
            
            # Set up headers based on provider
            if provider == "openai":
                self.headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            elif provider == "anthropic":
                self.headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
            elif provider == "openrouter":
                self.headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://isaac-sim-llm-assistant",
                    "X-Title": "Isaac Sim LLM Assistant"
                }
            elif provider == "ollama":
                self.headers = {
                    "Content-Type": "application/json"
                }
            
            # Create aiohttp session
            self.session = aiohttp.ClientSession()
            
            # Test connection
            await self._test_connection()
            
            carb.log_info(f"[LLM Interface] Connected to {provider} with model {self.model}")
            return True
            
        except Exception as e:
            carb.log_error(f"[LLM Interface] Failed to initialize {provider}: {str(e)}")
            return False
    
    async def _test_connection(self):
        """Test the LLM connection"""
        try:
            response = await self.generate_response("Hello! This is a connection test.", max_tokens=50)
            return True
        except Exception as e:
            raise Exception(f"Connection test failed: {str(e)}")
    
    async def generate_response(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        """Generate response from LLM"""
        try:
            if not self.session:
                raise Exception("LLM not initialized")
            
            # Build request based on provider
            if self.provider in ["openai", "openrouter"]:
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            elif self.provider == "anthropic":
                payload = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature
                }
            elif self.provider == "ollama":
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }
            
            async with self.session.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API Error {response.status}: {error_text}")
                
                result = await response.json()
                
                # Extract response based on provider
                if self.provider in ["openai", "openrouter"]:
                    return result["choices"][0]["message"]["content"]
                elif self.provider == "anthropic":
                    return result["content"][0]["text"]
                elif self.provider == "ollama":
                    return result["message"]["content"]
                
        except Exception as e:
            carb.log_error(f"[LLM Interface] Error generating response: {str(e)}")
            raise e
    
    async def generate_code(self, prompt: str, context: Dict = None) -> Dict[str, Any]:
        """Generate Isaac Sim code with enhanced prompting"""
        
        enhanced_prompt = f"""
You are an expert Isaac Sim developer. Generate Python code for the following request:
{prompt}

Current Context:
{json.dumps(context, indent=2) if context else "No context available"}

Requirements:
1. Generate complete, runnable Python code
2. Include all necessary imports
3. Add error handling
4. Use Isaac Sim 5.0.0 APIs (isaacsim.core.api, not omni.isaac)
5. Add helpful comments
6. Structure code in logical blocks

Respond with a JSON object:
{{
    "code": "python code here",
    "explanation": "brief explanation of what the code does",
    "dependencies": ["list", "of", "required", "extensions"],
    "safety_level": "safe|moderate|risky",
    "estimated_runtime": "seconds"
}}
"""
        
        try:
            response = await self.generate_response(enhanced_prompt, max_tokens=3000)
            
            # Try to parse JSON response
            try:
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.find("```", json_start)
                    json_str = response[json_start:json_end].strip()
                else:
                    json_str = response
                
                result = json.loads(json_str)
                
                # Validate structure
                required_keys = ["code", "explanation", "safety_level"]
                for key in required_keys:
                    if key not in result:
                        result[key] = "Not specified"
                
                return result
                
            except json.JSONDecodeError:
                # Fallback: extract code blocks manually
                return {
                    "code": self._extract_python_code(response),
                    "explanation": "Generated code from LLM response",
                    "dependencies": [],
                    "safety_level": "moderate",
                    "estimated_runtime": "unknown"
                }
                
        except Exception as e:
            carb.log_error(f"[LLM Interface] Error generating code: {str(e)}")
            return {
                "code": f"# Error: {str(e)}",
                "explanation": "Failed to generate code",
                "dependencies": [],
                "safety_level": "risky",
                "estimated_runtime": "0"
            }
    
    def _extract_python_code(self, text: str) -> str:
        """Extract Python code from markdown-formatted text"""
        if "```python" in text:
            start = text.find("```python") + 9
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        return text
    
    async def analyze_simulation(self, context: Dict, question: str) -> str:
        """Analyze simulation state and provide insights"""
        
        analysis_prompt = f"""
Analyze this Isaac Sim simulation state and answer the question:

Question: {question}

Simulation Context:
- Stage Info: {context.get('stage_info', {})}
- Timeline: {context.get('timeline_info', {})}
- Objects: {context.get('selected_prims', [])}
- Physics State: {context.get('physics_state', {})}
- Sensors: {context.get('sensors', [])}
- Robots: {context.get('robots', [])}

Provide a detailed analysis focusing on:
1. Current simulation state
2. Potential issues or improvements
3. Recommendations for optimization
4. Answer to the specific question

Be technical but accessible.
"""
        
        return await self.generate_response(analysis_prompt, max_tokens=1500)
    
    def get_available_models(self) -> List[str]:
        """Get available models for current provider"""
        if self.provider and self.provider in self.providers:
            return self.providers[self.provider]["models"]
        return []
    
    def get_providers(self) -> List[str]:
        """Get list of supported providers"""
        return list(self.providers.keys())
    
    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
            self.session = None
        carb.log_info("[LLM Interface] Cleaned up successfully")

# Singleton instance
_llm_interface = None

def get_llm_interface() -> LLMInterface:
    """Get global LLM interface instance"""
    global _llm_interface
    if _llm_interface is None:
        _llm_interface = LLMInterface()
    return _llm_interface 