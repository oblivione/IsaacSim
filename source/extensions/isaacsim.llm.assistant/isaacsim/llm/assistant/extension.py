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
from .llm_interface import get_llm_interface
from .recording_manager import get_recording_manager

# Try to import IsaacSim-specific components
try:
    from isaacsim.core.api import World
    ISAACCORE_AVAILABLE = True
except ImportError:
    ISAACCORE_AVAILABLE = False

try:
    from isaacsim.gui.components.element_wrappers import ScrollingWindow
    from isaacsim.gui.components.menu import make_menu_item_description
    ISAAC_GUI_AVAILABLE = True
except ImportError:
    ISAAC_GUI_AVAILABLE = False
    # Fallback to standard omni UI
    class ScrollingWindow:
        def __init__(self, title, width=400, height=300, visible=False, dockPreference=None):
            self.title = title
            self.visible = visible
            self._window = ui.Window(title, width=width, height=height, visible=visible)
            self.frame = self._window.frame
        
        def set_visibility_changed_fn(self, fn):
            pass

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
            dockPreference=ui.DockPreference.LEFT_BOTTOM if hasattr(ui, 'DockPreference') else None
        )
        self._window.set_visibility_changed_fn(self._on_window)
        
        # Menu integration
        try:
            if ISAAC_GUI_AVAILABLE:
                self._menu_items = [
                    make_menu_item_description(
                        ext_id, 
                        "LLM Assistant", 
                        lambda a=weakref.proxy(self): a._menu_callback()
                    )
                ]
            else:
                self._menu_items = [("LLM Assistant", lambda: self._menu_callback())]
            add_menu_items(self._menu_items, "Tools")
        except Exception as e:
            carb.log_warn(f"[LLM Extension] Could not add menu items: {e}")
            self._menu_items = []
        
        # Initialize LLM interface and recording manager
        self._llm_interface = get_llm_interface()
        self._recording_manager = get_recording_manager()
        self._chat_history = []
        
        # UI Models
        self._models = {}
        
        carb.log_info("[LLM Extension] Startup complete")
    
    def on_shutdown(self):
        """Clean up resources"""
        carb.log_info("[LLM Extension] Shutting down...")
        try:
            remove_menu_items(self._menu_items, "Tools")
        except:
            pass
        if self._window:
            self._window = None
        if self._llm_interface:
            asyncio.ensure_future(self._llm_interface.cleanup())
        if self._recording_manager and self._recording_manager.is_recording:
            self._recording_manager.stop_recording()
        gc.collect()
        carb.log_info("[LLM Extension] Shutdown complete")
    
    def _menu_callback(self):
        """Toggle window visibility"""
        self._window.visible = not self._window.visible
        if self._window.visible:
            self._build_ui()
    
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
                        style={"font_size": 18})
                ui.Spacer(height=10)
                
                # Status
                self._build_status_ui()
                
                # Chat area
                self._build_chat_ui()
                
                # Input area  
                self._build_input_ui()
                
                # LLM configuration
                self._build_config_ui()
                
                # Recording controls
                self._build_recording_ui()
                
                # Quick commands
                self._build_quick_commands_ui()
    
    def _build_status_ui(self):
        """Build status indicator"""
        with ui.HStack(height=30):
            ui.Label("Status:", width=60)
            self._status_label = ui.Label("Ready - Connect to an LLM provider to start")
    
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
                    multiline=True
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
                        0, "OpenAI", "Anthropic", "OpenRouter", "Local Ollama", "Azure OpenAI"
                    ).model
                
                # API Key input
                with ui.HStack():
                    ui.Label("API Key:", width=80)
                    self._models["api_key"] = ui.StringField().model
                
                # Model selection
                with ui.HStack():
                    ui.Label("Model:", width=80)
                    self._models["model_name"] = ui.StringField().model
                
                # Connect button
                ui.Button(
                    "Connect to LLM",
                    height=30,
                    clicked_fn=self._connect_llm
                )
                
                # Model refresh and status
                with ui.HStack():
                    ui.Button(
                        "Refresh Models",
                        width=120,
                        height=25,
                        clicked_fn=self._refresh_models
                    )
                    self._connection_status = ui.Label("Not connected", style={"color": 0xFFFF6B6B})
    
    def _build_recording_ui(self):
        """Build recording controls UI"""
        with ui.CollapsableFrame("🎥 Simulation Recording", collapsed=True):
            with ui.VStack(spacing=5):
                
                # Recording status
                with ui.HStack():
                    ui.Label("Status:", width=80)
                    self._recording_status = ui.Label("Not recording")
                
                # Recording name input
                with ui.HStack():
                    ui.Label("Name:", width=80)
                    self._models["recording_name"] = ui.StringField(
                        placeholder_text="Enter recording name (optional)..."
                    ).model
                
                # Recording controls
                with ui.HStack():
                    self._start_recording_btn = ui.Button(
                        "🔴 Start Recording",
                        width=120,
                        height=30,
                        clicked_fn=self._start_recording
                    )
                    self._stop_recording_btn = ui.Button(
                        "⏹️ Stop Recording",
                        width=120,
                        height=30,
                        clicked_fn=self._stop_recording,
                        enabled=False
                    )
                
                # Recording list
                with ui.CollapsableFrame("📁 Previous Recordings", collapsed=True):
                    self._recordings_scroll = ui.ScrollingFrame(height=150)
                    with self._recordings_scroll:
                        self._recordings_stack = ui.VStack(spacing=2)
                        self._refresh_recordings_list()
                
                # Analysis controls
                with ui.HStack():
                    ui.Button(
                        "🔍 Analyze Recording",
                        width=140,
                        height=25,
                        clicked_fn=self._analyze_recording
                    )
                    ui.Button(
                        "📊 Generate Report",
                        width=140,
                        height=25,
                        clicked_fn=self._generate_report
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
                    ui.Button("Create Sphere", clicked_fn=lambda: self._quick_command("Create a sphere at position (1,0,1)"))
                
                # Advanced commands
                with ui.HStack():
                    ui.Button("Generate Code", clicked_fn=lambda: self._quick_command("Generate Python code to create a robotic pick and place task"))
                    ui.Button("Analyze Scene", clicked_fn=lambda: self._quick_command("Analyze the current simulation for potential issues and improvements"))
                
                # Recording shortcuts
                with ui.HStack():
                    ui.Button("Record & Analyze", clicked_fn=self._record_and_analyze)
                    ui.Button("Code + Execute", clicked_fn=self._advanced_code_generation)
    
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
            self._update_status("Processing...")
            
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
            
            self._update_status("Ready")
            
        except Exception as e:
            self._add_chat_message("Error", f"Failed to process query: {str(e)}")
            self._update_status("Error")
            carb.log_error(f"[LLM Extension] Error processing query: {str(e)}")
    
    def _get_isaac_sim_context(self):
        """Gather current Isaac Sim state for LLM context"""
        context = {
            "stage_info": {},
            "timeline_info": {},
            "selected_prims": [],
        }
        
        try:
            # Get current stage
            stage = self._usd_context.get_stage()
            if stage:
                prims = list(stage.Traverse())
                context["stage_info"] = {
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
Be concise but helpful.
        """
        
        return f"{system_prompt}\n\nUser Query: {query}"
    
    async def _call_llm_api(self, prompt: str):
        """Call LLM API using enhanced interface"""
        try:
            # Check if LLM is connected
            if hasattr(self._llm_interface, 'session') and self._llm_interface.session:
                # Use enhanced query processing
                if hasattr(self, '_enhanced_mode') and self._enhanced_mode:
                    self._enhanced_mode = False  # Reset flag
                    return await self._enhanced_llm_query(prompt.split('User Query: ')[-1])
                else:
                    return await self._llm_interface.generate_response(prompt)
            else:
                # Fallback to mock responses for demo
                return self._mock_llm_response(prompt)
                
        except Exception as e:
            carb.log_error(f"[LLM Extension] Error in LLM API call: {str(e)}")
            return f"❌ LLM API Error: {str(e)}\n\nTry connecting to an LLM provider first."
    
    def _mock_llm_response(self, prompt: str):
        """Mock LLM responses for demo mode"""
        query_lower = prompt.lower()
        
        if "create" in query_lower and "cube" in query_lower:
            return """🎯 **Demo Mode Response**

I'll help you create a cube! Here's the Python code:

```python
import omni.kit.commands
from pxr import UsdGeom, Gf

# Create a cube primitive
omni.kit.commands.execute('CreateMeshPrimCommand',
    prim_type='Cube'
)

# Get the stage and cube prim
stage = omni.usd.get_context().get_stage()
cube_prim = stage.GetPrimAtPath('/World/Cube')

# Set position
if cube_prim:
    xform = UsdGeom.Xformable(cube_prim)
    transform_matrix = Gf.Matrix4d()
    transform_matrix.SetTranslateOnly(Gf.Vec3d(0, 0, 1))
    xform.SetLocalTransformation(transform_matrix)
```

✅ This will create a cube in your scene at position (0,0,1)!

💡 **Tip:** Connect to OpenRouter for free LLM access or other providers for enhanced capabilities."""
        
        elif "openrouter" in query_lower:
            return """🌐 **OpenRouter Integration**

OpenRouter provides access to multiple LLMs through a single API:

**Free Models Available:**
- Meta Llama 3.1 8B (Free)
- Various open-source models

**Premium Models:**
- GPT-4, Claude 3.5 Sonnet
- Gemini Pro, Mixtral 8x7B

**How to Connect:**
1. Visit openrouter.ai and create account
2. Get your API key
3. Select 'OpenRouter' as provider
4. Enter API key and choose model
5. Connect and start chatting!

**Benefits:**
- Multiple models in one interface
- Often cheaper than direct APIs
- Great for experimentation"""
        
        elif "scene" in query_lower and ("what" in query_lower or "describe" in query_lower):
            context = self._get_isaac_sim_context()
            prims = context.get('selected_prims', [])
            return f"""📊 **Scene Analysis**

Current scene contains **{len(prims)}** objects:

{chr(10).join(f"• {prim}" for prim in prims[:10])}
{"..." if len(prims) > 10 else ""}

**Recording Status:** {'🔴 Recording' if self._recording_manager.is_recording else '⚪ Not recording'}

💡 **Suggestions:**
- Use recording to capture simulation data
- Connect to LLM for deeper analysis
- Try "Generate Code" for scene automation"""
        
        elif "record" in query_lower:
            status = self._recording_manager.get_recording_status()
            return f"""🎥 **Recording System**

**Status:** {'🔴 Recording' if status['is_recording'] else '⚪ Ready'}
**Current Recording:** {status.get('recording_id', 'None')}
**Duration:** {status.get('duration', 0):.1f}s

**Features:**
- Automatic timeline capture
- Physics data recording  
- Robot state tracking
- Sensor data logging
- AI-powered analysis

**Quick Actions:**
- Click 'Record & Analyze' for 30s auto-recording
- Use recording controls in the panel
- Generate reports from recorded data"""
        
        else:
            query_excerpt = prompt.split('User Query: ')[-1][:100]
            return f"""🤖 **LLM Assistant Ready**

I received: "{query_excerpt}..."

**🔗 Connect to LLM Provider:**
- **OpenRouter** (Recommended): Free access to Llama 3.1
- **OpenAI**: GPT-4, GPT-3.5-turbo  
- **Anthropic**: Claude 3.5 Sonnet
- **Local Ollama**: Run models locally

**✨ Enhanced Features:**
- 🎯 Advanced code generation
- 🎥 Simulation recording & analysis
- 📊 Automated reporting
- 🔍 Scene understanding

**🚀 Try these commands:**
- "Create a robotic pick and place scene"
- "Generate Python code for physics simulation"  
- "Analyze my current simulation recording"
- "What's the best way to set up sensors?"

Connect to an LLM provider above for full AI capabilities!"""
    
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
                # Sender label
                ui.Label(f"{sender}:", width=60)
                ui.Label(message, word_wrap=True)
    
    def _update_status(self, status: str):
        """Update status label"""
        if hasattr(self, '_status_label'):
            self._status_label.text = status
    
    def _connect_llm(self):
        """Initialize LLM connection"""
        provider_idx = self._models["api_provider"].get_item_value_model().get_value_as_int()
        api_key = self._models["api_key"].get_value_as_string()
        model_name = self._models["model_name"].get_value_as_string()
        
        providers = ["OpenAI", "Anthropic", "Local Ollama", "Azure OpenAI"]
        provider = providers[provider_idx]
        
        # Initialize your LLM interface here
        self._add_chat_message("System", f"Connecting to {provider}...")
        self._update_status(f"Connected to {provider}")
        
        # Initialize real LLM connection
        asyncio.ensure_future(self._initialize_llm_connection(provider, api_key, model_name))
    
    async def _initialize_llm_connection(self, provider: str, api_key: str, model_name: str):
        """Initialize LLM connection asynchronously"""
        try:
            success = await self._llm_interface.initialize(provider, api_key, model_name)
            if success:
                self._connection_status.text = f"Connected to {provider}"
                self._connection_status.style = {"color": 0xFF66BB6A}
                self._add_chat_message("System", f"✅ Successfully connected to {provider} with model {model_name}")
            else:
                self._connection_status.text = "Connection failed"
                self._connection_status.style = {"color": 0xFFFF6B6B}
                self._add_chat_message("System", f"❌ Failed to connect to {provider}")
        except Exception as e:
            self._connection_status.text = "Connection error"
            self._connection_status.style = {"color": 0xFFFF6B6B}
            self._add_chat_message("System", f"❌ Connection error: {str(e)}")
    
    def _refresh_models(self):
        """Refresh available models for selected provider"""
        try:
            provider_idx = self._models["api_provider"].get_item_value_model().get_value_as_int()
            providers = ["OpenAI", "Anthropic", "OpenRouter", "Local Ollama", "Azure OpenAI"]
            provider_map = {"OpenAI": "openai", "Anthropic": "anthropic", "OpenRouter": "openrouter", "Local Ollama": "ollama", "Azure OpenAI": "openai"}
            
            provider = provider_map.get(providers[provider_idx], "openai")
            models = self._llm_interface.get_available_models() if hasattr(self._llm_interface, 'providers') else []
            
            if hasattr(self._llm_interface, 'providers') and provider in self._llm_interface.providers:
                models = self._llm_interface.providers[provider]["models"]
                model_text = ", ".join(models[:3]) + ("..." if len(models) > 3 else "")
                self._add_chat_message("System", f"Available models for {providers[provider_idx]}: {model_text}")
            
        except Exception as e:
            carb.log_error(f"[LLM Extension] Error refreshing models: {str(e)}")
    
    def _start_recording(self):
        """Start simulation recording"""
        try:
            recording_name = self._models["recording_name"].get_value_as_string()
            result = self._recording_manager.start_recording(recording_name or None)
            
            if result["success"]:
                self._recording_status.text = f"Recording: {result['recording_id']}"
                self._start_recording_btn.enabled = False
                self._stop_recording_btn.enabled = True
                self._add_chat_message("System", f"🔴 {result['message']}")
            else:
                self._add_chat_message("System", f"❌ {result['message']}")
                
        except Exception as e:
            self._add_chat_message("System", f"❌ Failed to start recording: {str(e)}")
    
    def _stop_recording(self):
        """Stop simulation recording"""
        try:
            result = self._recording_manager.stop_recording()
            
            if result["success"]:
                self._recording_status.text = "Not recording"
                self._start_recording_btn.enabled = True
                self._stop_recording_btn.enabled = False
                self._add_chat_message("System", f"⏹️ {result['message']}")
                self._refresh_recordings_list()
                
                # Offer analysis
                self._add_chat_message("System", "Recording saved! Click 'Analyze Recording' to get AI insights.")
            else:
                self._add_chat_message("System", f"❌ {result['message']}")
                
        except Exception as e:
            self._add_chat_message("System", f"❌ Failed to stop recording: {str(e)}")
    
    def _refresh_recordings_list(self):
        """Refresh the recordings list"""
        try:
            if hasattr(self, '_recordings_stack'):
                self._recordings_stack.clear()
                
                recordings = self._recording_manager.get_recordings()
                
                with self._recordings_stack:
                    if not recordings:
                        ui.Label("No recordings found", style={"color": 0xFF999999})
                    else:
                        for recording in recordings[:5]:  # Show last 5
                            with ui.HStack(height=25):
                                ui.Label(f"📹 {recording.get('recording_id', 'Unknown')}", width=200)
                                ui.Label(f"{recording.get('duration', 0):.1f}s", width=50)
                                ui.Button("View", width=40, height=20, 
                                        clicked_fn=lambda r=recording: self._view_recording(r))
                        
        except Exception as e:
            carb.log_error(f"[LLM Extension] Error refreshing recordings: {str(e)}")
    
    def _view_recording(self, recording):
        """View recording details"""
        try:
            details = f"""
Recording: {recording.get('recording_id', 'Unknown')}
Duration: {recording.get('duration', 0):.1f} seconds
Frames: {recording.get('frame_count', 0)}
Physics Events: {recording.get('physics_events', 0)}
Robot Events: {recording.get('robot_events', 0)}
"""
            self._add_chat_message("System", f"📊 Recording Details:\n{details}")
        except Exception as e:
            self._add_chat_message("System", f"❌ Error viewing recording: {str(e)}")
    
    def _analyze_recording(self):
        """Analyze recording with LLM"""
        try:
            recordings = self._recording_manager.get_recordings()
            if not recordings:
                self._add_chat_message("System", "❌ No recordings available to analyze")
                return
            
            latest_recording = recordings[0]
            
            # Send to LLM for analysis
            analysis_query = f"Analyze this simulation recording and provide insights: {json.dumps(latest_recording, indent=2)}"
            self._models["user_input"].set_value(analysis_query)
            self._send_query()
            
        except Exception as e:
            self._add_chat_message("System", f"❌ Error analyzing recording: {str(e)}")
    
    def _generate_report(self):
        """Generate detailed report"""
        try:
            recordings = self._recording_manager.get_recordings()
            if not recordings:
                self._add_chat_message("System", "❌ No recordings available for report")
                return
            
            # Generate comprehensive report
            report_query = "Generate a comprehensive simulation analysis report based on the available recording data, including performance metrics, recommendations, and potential improvements."
            self._models["user_input"].set_value(report_query)
            self._send_query()
            
        except Exception as e:
            self._add_chat_message("System", f"❌ Error generating report: {str(e)}")
    
    def _record_and_analyze(self):
        """Start recording and prepare for analysis"""
        try:
            if self._recording_manager.is_recording:
                self._add_chat_message("System", "⚠️ Already recording. Stop current recording first.")
                return
            
            # Start recording
            result = self._recording_manager.start_recording("auto_analysis")
            if result["success"]:
                self._recording_status.text = f"Recording: {result['recording_id']}"
                self._start_recording_btn.enabled = False
                self._stop_recording_btn.enabled = True
                self._add_chat_message("System", "🔴 Recording started. Will automatically analyze when stopped.")
                
                # Schedule auto-stop after 30 seconds
                asyncio.ensure_future(self._auto_stop_and_analyze())
            else:
                self._add_chat_message("System", f"❌ {result['message']}")
                
        except Exception as e:
            self._add_chat_message("System", f"❌ Error in record and analyze: {str(e)}")
    
    async def _auto_stop_and_analyze(self):
        """Auto stop recording after 30 seconds and analyze"""
        try:
            await asyncio.sleep(30)  # Record for 30 seconds
            
            if self._recording_manager.is_recording:
                result = self._recording_manager.stop_recording()
                if result["success"]:
                    self._recording_status.text = "Not recording"
                    self._start_recording_btn.enabled = True
                    self._stop_recording_btn.enabled = False
                    self._refresh_recordings_list()
                    
                    # Auto analyze
                    await asyncio.sleep(1)  # Wait a moment
                    self._analyze_recording()
                    
        except Exception as e:
            carb.log_error(f"[LLM Extension] Error in auto stop and analyze: {str(e)}")
    
    def _advanced_code_generation(self):
        """Advanced code generation with execution"""
        try:
            query = "Generate and execute Python code to create an interesting Isaac Sim scene with robots, objects, and physics. Make it visually appealing and functionally interesting."
            self._models["user_input"].set_value(query)
            
            # Set flag for enhanced code generation
            self._enhanced_mode = True
            self._send_query()
            
        except Exception as e:
            self._add_chat_message("System", f"❌ Error in advanced code generation: {str(e)}")
            
    async def _enhanced_llm_query(self, query: str):
        """Enhanced LLM query with better code generation"""
        try:
            # Get comprehensive context
            context = self._get_isaac_sim_context()
            
            # Check if this is a code generation request
            if any(keyword in query.lower() for keyword in ["generate", "create", "code", "python", "script"]):
                # Use enhanced code generation
                result = await self._llm_interface.generate_code(query, context)
                
                response = f"""💻 **Code Generation Result**

**Explanation:** {result.get('explanation', 'N/A')}
**Safety Level:** {result.get('safety_level', 'Unknown')}
**Estimated Runtime:** {result.get('estimated_runtime', 'Unknown')}

**Generated Code:**
```python
{result.get('code', '# No code generated')}
```

**Dependencies:** {', '.join(result.get('dependencies', []))}
"""
                
                # Execute if safe
                if result.get('safety_level') in ['safe', 'moderate'] and result.get('code'):
                    try:
                        exec(result['code'])
                        response += "\n\n✅ **Code executed successfully!**"
                    except Exception as e:
                        response += f"\n\n❌ **Execution error:** {str(e)}"
                
                return response
            else:
                # Use regular analysis
                return await self._llm_interface.analyze_simulation(context, query)
                
        except Exception as e:
            return f"❌ Enhanced query failed: {str(e)}" 