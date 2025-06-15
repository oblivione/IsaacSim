# SPDX-FileCopyrightText: Copyright (c) 2025 YOUR_NAME. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import gc
import weakref
import omni.ext
import omni.ui as ui
import omni.kit.commands
import omni.timeline
import omni.usd
from isaacsim.gui.components.element_wrappers import ScrollingWindow
from isaacsim.gui.components.menu import make_menu_item_description
from omni.kit.menu.utils import add_menu_items, remove_menu_items

class LLMExtension(omni.ext.IExt):
    """
    Isaac Sim Extension for LLM Integration
    Provides natural language interface to Isaac Sim functionality
    """
    
    def on_startup(self, ext_id: str):
        """Initialize the LLM extension"""
        
        self._ext_id = ext_id
        self._usd_context = omni.usd.get_context()
        
        # Create main window
        self._window = ScrollingWindow(
            title="LLM Assistant for Isaac Sim",
            width=800,
            height=600,
            visible=False,
            dockPreference=ui.DockPreference.LEFT_BOTTOM
        )
        self._window.set_visibility_changed_fn(self._on_window)
        
        # Menu integration
        self._menu_items = [
            make_menu_item_description(
                ext_id, 
                "LLM Assistant", 
                lambda a=weakref.proxy(self): a._menu_callback()
            )
        ]
        add_menu_items(self._menu_items, "Tools")
        
        # Initialize LLM interface
        self._llm_interface = None
        self._chat_history = []
        
        # UI Models
        self._models = {}
        
        print("[LLM Extension] Startup complete")
    
    def on_shutdown(self):
        """Clean up resources"""
        remove_menu_items(self._menu_items, "Tools")
        if self._window:
            self._window = None
        if self._llm_interface:
            self._llm_interface.cleanup()
        gc.collect()
        print("[LLM Extension] Shutdown complete")
    
    def _menu_callback(self):
        """Toggle window visibility"""
        self._window.visible = not self._window.visible
    
    def _on_window(self, visible):
        """Handle window visibility changes"""
        if self._window.visible:
            self._build_ui()
    
    def _build_ui(self):
        """Build the main UI"""
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                
                # Header
                ui.Label("🤖 LLM Assistant for Isaac Sim", 
                        style={"font_size": 18, "font_weight": "bold"})
                ui.Spacer(height=10)
                
                # Chat area
                self._build_chat_ui()
                
                # Input area  
                self._build_input_ui()
                
                # LLM configuration
                self._build_config_ui()
    
    def _build_chat_ui(self):
        """Build chat history display"""
        with ui.CollapsableFrame("Chat History", height=300):
            # Chat messages scroll area
            self._chat_scroll = ui.ScrollingFrame(
                height=250,
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
            )
            with self._chat_scroll:
                self._chat_stack = ui.VStack(spacing=5)
    
    def _build_input_ui(self):
        """Build input area for user queries"""
        with ui.CollapsableFrame("Ask the LLM", collapsed=False):
            with ui.VStack(spacing=5):
                
                # Text input
                self._models["user_input"] = ui.StringField(
                    height=80,
                    multiline=True,
                    placeholder_text="Ask me anything about Isaac Sim...\nE.g., 'Create a cube at position (1,1,1)' or 'What robots are in the scene?'"
                ).model
                
                # Send button
                with ui.HStack():
                    ui.Spacer()
                    ui.Button(
                        "Send Query",
                        width=100,
                        height=30,
                        clicked_fn=self._send_query
                    )
    
    def _build_config_ui(self):
        """Build LLM configuration UI"""
        with ui.CollapsableFrame("LLM Configuration", collapsed=True):
            with ui.VStack(spacing=5):
                
                # API Provider selection
                with ui.HStack():
                    ui.Label("Provider:", width=80)
                    self._models["api_provider"] = ui.ComboBox(
                        0, "OpenAI", "Anthropic", "Local Ollama", "Azure OpenAI"
                    ).model
                
                # API Key input
                with ui.HStack():
                    ui.Label("API Key:", width=80)
                    self._models["api_key"] = ui.StringField(
                        password_mode=True,
                        placeholder_text="Enter your API key..."
                    ).model
                
                # Model selection
                with ui.HStack():
                    ui.Label("Model:", width=80)
                    self._models["model_name"] = ui.StringField(
                        placeholder_text="gpt-4, claude-3-sonnet, llama2..."
                    ).model
                
                # Connect button
                ui.Button(
                    "Connect to LLM",
                    height=30,
                    clicked_fn=self._connect_llm
                )
    
    def _send_query(self):
        """Send user query to LLM"""
        user_input = self._models["user_input"].get_value_as_string()
        if not user_input.strip():
            return
        
        # Add user message to chat
        self._add_chat_message("User", user_input)
        
        # Clear input
        self._models["user_input"].set_value("")
        
        # Process with LLM (async)
        asyncio.ensure_future(self._process_llm_query(user_input))
    
    async def _process_llm_query(self, query: str):
        """Process query with LLM"""
        try:
            # Get Isaac Sim context
            context = self._get_isaac_sim_context()
            
            # Build prompt with context
            full_prompt = self._build_prompt(query, context)
            
            # Send to LLM (you'll implement this)
            response = await self._call_llm_api(full_prompt)
            
            # Parse and execute response
            await self._execute_llm_response(response)
            
            # Add response to chat
            self._add_chat_message("LLM", response)
            
        except Exception as e:
            self._add_chat_message("Error", f"Failed to process query: {str(e)}")
    
    def _get_isaac_sim_context(self):
        """Gather current Isaac Sim state for LLM context"""
        context = {
            "stage_info": {},
            "timeline_info": {},
            "selected_prims": [],
            "available_robots": [],
            "sensors": [],
            "physics_state": {}
        }
        
        # Get current stage
        stage = self._usd_context.get_stage()
        if stage:
            context["stage_info"] = {
                "path": str(stage.GetRootLayer().identifier),
                "prim_count": len(list(stage.Traverse()))
            }
            
            # Get all prims
            context["selected_prims"] = [
                str(prim.GetPath()) for prim in stage.Traverse()
                if prim.IsValid()
            ]
        
        # Add timeline info
        timeline = omni.timeline.get_timeline_interface()
        context["timeline_info"] = {
            "is_playing": timeline.is_playing(),
            "current_time": timeline.get_current_time()
        }
        
        return context
    
    def _build_prompt(self, query: str, context: dict):
        """Build complete prompt for LLM"""
        system_prompt = """
You are an AI assistant specialized in NVIDIA Isaac Sim robotics simulation.
You can help users with:
1. Creating and manipulating 3D objects and robots
2. Setting up physics simulations
3. Configuring sensors and cameras
4. Writing OmniGraph node networks
5. Controlling robot movements
6. Generating Python code for Isaac Sim

Current Isaac Sim Context:
- Stage: {stage_info}
- Timeline: {timeline_info}
- Objects in scene: {selected_prims}

Respond with specific Isaac Sim commands or Python code when appropriate.
Use the isaacsim.core.api for most operations.
        """.format(**context)
        
        return f"{system_prompt}\n\nUser Query: {query}"
    
    async def _call_llm_api(self, prompt: str):
        """Call LLM API - implement based on your chosen provider"""
        # This is where you'd integrate with:
        # - OpenAI API
        # - Anthropic Claude API  
        # - Local Ollama
        # - Azure OpenAI
        # etc.
        
        # Placeholder response
        return "LLM response would go here. Implement your API integration."
    
    async def _execute_llm_response(self, response: str):
        """Execute LLM commands in Isaac Sim"""
        # Parse response for Isaac Sim commands
        # Execute Python code safely
        # Update scene based on LLM suggestions
        pass
    
    def _add_chat_message(self, sender: str, message: str):
        """Add message to chat UI"""
        with self._chat_stack:
            with ui.HStack(height=0):
                ui.Label(f"{sender}:", width=50, style={"font_weight": "bold"})
                ui.Label(message, word_wrap=True)
    
    def _connect_llm(self):
        """Initialize LLM connection"""
        provider = self._models["api_provider"].get_item_value_model().get_value_as_int()
        api_key = self._models["api_key"].get_value_as_string()
        model_name = self._models["model_name"].get_value_as_string()
        
        # Initialize your LLM interface here
        self._add_chat_message("System", f"Connecting to LLM provider...") 