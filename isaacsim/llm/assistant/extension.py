# SPDX-FileCopyrightText: Copyright (c) 2025 YOUR_NAME. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import gc
import weakref
import json
import omni.ext
import omni.ui as ui
import omni.kit.commands
import omni.timeline
import omni.usd
import carb
from isaacsim.gui.components.element_wrappers import ScrollingWindow
from isaacsim.gui.components.menu import make_menu_item_description
from omni.kit.menu.utils import add_menu_items, remove_menu_items

class Extension(omni.ext.IExt):
    """
    Isaac Sim Extension for LLM Integration
    Provides natural language interface to Isaac Sim functionality
    """
    
    def on_startup(self, ext_id: str):
        """Initialize the LLM extension"""
        
        self._ext_id = ext_id
        self._usd_context = omni.usd.get_context()
        
        carb.log_info("[LLM Extension] Starting up...")
        
        # Create main window
        self._window = ScrollingWindow(
            title="🤖 LLM Assistant for Isaac Sim",
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
        
        carb.log_info("[LLM Extension] Startup complete")
    
    def on_shutdown(self):
        """Clean up resources"""
        carb.log_info("[LLM Extension] Shutting down...")
        remove_menu_items(self._menu_items, "Tools")
        if self._window:
            self._window = None
        if self._llm_interface:
            # self._llm_interface.cleanup()
            pass
        gc.collect()
        carb.log_info("[LLM Extension] Shutdown complete")
    
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
                
                # Status
                self._build_status_ui()
                
                # Chat area
                self._build_chat_ui()
                
                # Input area  
                self._build_input_ui()
                
                # LLM configuration
                self._build_config_ui()
                
                # Quick commands
                self._build_quick_commands_ui()
    
    def _build_status_ui(self):
        """Build status indicator"""
        with ui.HStack(height=30):
            ui.Label("Status:", width=60)
            self._status_label = ui.Label("Ready - Connect to an LLM provider to start", 
                                        style={"color": 0xFF999999})
    
    def _build_chat_ui(self):
        """Build chat history display"""
        with ui.CollapsableFrame("Chat History", height=250):
            # Chat messages scroll area
            self._chat_scroll = ui.ScrollingFrame(
                height=200,
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
            )
            with self._chat_scroll:
                self._chat_stack = ui.VStack(spacing=5)
                # Add welcome message
                self._add_chat_message("System", "Welcome! Ask me anything about Isaac Sim...")
    
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
                    ui.Button(
                        "Clear Chat",
                        width=100,
                        height=30,
                        clicked_fn=self._clear_chat
                    )
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
    
    def _build_quick_commands_ui(self):
        """Build quick command buttons"""
        with ui.CollapsableFrame("Quick Commands", collapsed=True):
            with ui.VStack(spacing=5):
                
                # Scene commands
                with ui.HStack():
                    ui.Button("Describe Scene", clicked_fn=lambda: self._quick_command("What objects are currently in the scene?"))
                    ui.Button("Clear Scene", clicked_fn=lambda: self._quick_command("Clear all objects from the scene"))
                
                # Object creation
                with ui.HStack():
                    ui.Button("Create Cube", clicked_fn=lambda: self._quick_command("Create a cube at position (0,0,1)"))
                    ui.Button("Create Robot", clicked_fn=lambda: self._quick_command("Load a Franka robot in the scene"))
                
                # Simulation control
                with ui.HStack():
                    ui.Button("Start Simulation", clicked_fn=lambda: self._quick_command("Start the physics simulation"))
                    ui.Button("Stop Simulation", clicked_fn=lambda: self._quick_command("Stop the physics simulation"))
    
    def _quick_command(self, command: str):
        """Execute a quick command"""
        self._models["user_input"].set_value(command)
        self._send_query()
    
    def _clear_chat(self):
        """Clear chat history"""
        self._chat_history = []
        # Clear UI
        if hasattr(self, '_chat_stack'):
            self._chat_stack.clear()
            with self._chat_stack:
                self._add_chat_message("System", "Chat cleared. How can I help you?")
    
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
            self._update_status("Processing...", 0xFF3366FF)
            
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
            
            self._update_status("Ready", 0xFF66BB6A)
            
        except Exception as e:
            self._add_chat_message("Error", f"Failed to process query: {str(e)}")
            self._update_status("Error", 0xFFFF6B6B)
            carb.log_error(f"[LLM Extension] Error processing query: {str(e)}")
    
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
        
        try:
            # Get current stage
            stage = self._usd_context.get_stage()
            if stage:
                prims = list(stage.Traverse())
                context["stage_info"] = {
                    "path": str(stage.GetRootLayer().identifier),
                    "prim_count": len(prims)
                }
                
                # Get all prims (limited to avoid huge context)
                context["selected_prims"] = [
                    str(prim.GetPath()) for prim in prims[:20]  # Limit to first 20
                    if prim.IsValid()
                ]
            
            # Add timeline info
            timeline = omni.timeline.get_timeline_interface()
            context["timeline_info"] = {
                "is_playing": timeline.is_playing(),
                "current_time": timeline.get_current_time()
            }
        except Exception as e:
            carb.log_warn(f"[LLM Extension] Error getting context: {str(e)}")
        
        return context
    
    def _build_prompt(self, query: str, context: dict):
        """Build complete prompt for LLM"""
        system_prompt = f"""
You are an AI assistant specialized in NVIDIA Isaac Sim robotics simulation.
You can help users with:
1. Creating and manipulating 3D objects and robots
2. Setting up physics simulations
3. Configuring sensors and cameras
4. Writing OmniGraph node networks
5. Controlling robot movements
6. Generating Python code for Isaac Sim

Current Isaac Sim Context:
- Stage: {context.get('stage_info', {})}
- Timeline: {context.get('timeline_info', {})}
- Objects in scene: {context.get('selected_prims', [])}

Respond with specific Isaac Sim commands or Python code when appropriate.
Use the isaacsim.core.api for most operations.
Be concise but helpful.
        """
        
        return f"{system_prompt}\n\nUser Query: {query}"
    
    async def _call_llm_api(self, prompt: str):
        """Call LLM API - implement based on your chosen provider"""
        # This is a placeholder - you'll implement your API integration here
        
        # For now, return a mock response based on common queries
        query_lower = prompt.lower()
        
        if "create" in query_lower and "cube" in query_lower:
            return """I'll help you create a cube! Here's the Python code:

```python
from isaacsim.core.api.objects import VisualCuboid
from isaacsim.core.api import World

# Create a cube at position (0, 0, 1)
world = World.instance()
cube = VisualCuboid(
    prim_path="/World/cube",
    position=(0, 0, 1),
    size=0.5,
    color=(1.0, 0.0, 0.0)  # Red color
)
world.scene.add(cube)
```

This will create a red cube in your scene!"""
        
        elif "scene" in query_lower and ("what" in query_lower or "describe" in query_lower):
            context = self._get_isaac_sim_context()
            prims = context.get('selected_prims', [])
            return f"Current scene contains {len(prims)} objects:\n" + "\n".join(f"- {prim}" for prim in prims[:10])
        
        else:
            return f"I received your query: '{prompt.split('User Query: ')[-1]}'\n\nTo fully respond, please connect to a real LLM provider in the configuration panel above."
    
    async def _execute_llm_response(self, response: str):
        """Execute LLM commands in Isaac Sim"""
        # Parse response for Python code blocks
        if "```python" in response:
            try:
                # Extract code block
                code_start = response.find("```python") + 9
                code_end = response.find("```", code_start)
                if code_end != -1:
                    code = response[code_start:code_end].strip()
                    carb.log_info(f"[LLM Extension] Executing code: {code}")
                    
                    # Execute safely (in a real implementation, add more safety checks)
                    exec(code)
            except Exception as e:
                carb.log_error(f"[LLM Extension] Error executing code: {str(e)}")
    
    def _add_chat_message(self, sender: str, message: str):
        """Add message to chat UI"""
        with self._chat_stack:
            with ui.HStack(height=0):
                # Sender label with color coding
                color = 0xFF66BB6A if sender == "User" else 0xFF42A5F5 if sender == "LLM" else 0xFFFF6B6B if sender == "Error" else 0xFF999999
                ui.Label(f"{sender}:", width=60, style={"font_weight": "bold", "color": color})
                ui.Label(message, word_wrap=True)
    
    def _update_status(self, status: str, color: int = 0xFF999999):
        """Update status label"""
        if hasattr(self, '_status_label'):
            self._status_label.text = status
            self._status_label.style = {"color": color}
    
    def _connect_llm(self):
        """Initialize LLM connection"""
        provider_idx = self._models["api_provider"].get_item_value_model().get_value_as_int()
        api_key = self._models["api_key"].get_value_as_string()
        model_name = self._models["model_name"].get_value_as_string()
        
        providers = ["OpenAI", "Anthropic", "Local Ollama", "Azure OpenAI"]
        provider = providers[provider_idx]
        
        # Initialize your LLM interface here
        self._add_chat_message("System", f"Connecting to {provider}...")
        self._update_status(f"Connected to {provider}", 0xFF66BB6A)
        
        # TODO: Implement actual API connections
        carb.log_info(f"[LLM Extension] Would connect to {provider} with model {model_name}") 