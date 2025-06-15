# SPDX-FileCopyrightText: Copyright (c) 2025 YOUR_NAME. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import carb
import omni.timeline
import omni.usd
import omni.kit.commands

try:
    import omni.kit.stagerecorder.core as stage_recorder
    STAGE_RECORDER_AVAILABLE = True
except ImportError:
    STAGE_RECORDER_AVAILABLE = False

try:
    import omni.replicator.core as rep
    REPLICATOR_AVAILABLE = True
except ImportError:
    REPLICATOR_AVAILABLE = False

class RecordingManager:
    """Manages simulation recording and analysis for Isaac Sim"""
    
    def __init__(self):
        self.is_recording = False
        self.recording_start_time = None
        self.recording_data = {}
        self.recording_path = "/tmp/isaac_sim_recordings"
        self.current_recording_id = None
        
        # Ensure recording directory exists
        os.makedirs(self.recording_path, exist_ok=True)
        
        self._timeline = omni.timeline.get_timeline_interface()
        self._usd_context = omni.usd.get_context()
        
        # Recording configuration
        self.recording_config = {
            "capture_frequency": 30,  # Hz
            "capture_screenshots": True,
            "capture_physics_data": True,
            "capture_robot_data": True,
            "capture_sensor_data": True,
            "max_recording_duration": 300,  # 5 minutes max
        }
    
    def start_recording(self, recording_name: str = None) -> Dict[str, Any]:
        """Start recording simulation"""
        if self.is_recording:
            return {"success": False, "message": "Already recording"}
        
        try:
            # Generate recording ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_recording_id = recording_name or f"recording_{timestamp}"
            
            # Create recording directory
            recording_dir = os.path.join(self.recording_path, self.current_recording_id)
            os.makedirs(recording_dir, exist_ok=True)
            
            # Initialize recording data
            self.recording_data = {
                "recording_id": self.current_recording_id,
                "start_time": timestamp,
                "timeline_data": [],
                "physics_data": [],
                "robot_data": [],
                "sensor_data": [],
                "screenshots": [],
                "metadata": {
                    "recording_dir": recording_dir,
                    "isaac_sim_version": "5.0.0",
                    "stage_path": str(self._usd_context.get_stage_url()),
                }
            }
            
            # Start stage recorder if available
            if STAGE_RECORDER_AVAILABLE:
                self._start_stage_recorder(recording_dir)
            
            # Start data collection
            self.is_recording = True
            self.recording_start_time = time.time()
            
            # Schedule periodic data capture
            asyncio.ensure_future(self._recording_loop())
            
            carb.log_info(f"[Recording Manager] Started recording: {self.current_recording_id}")
            
            return {
                "success": True,
                "recording_id": self.current_recording_id,
                "recording_dir": recording_dir,
                "message": f"Recording started: {self.current_recording_id}"
            }
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Failed to start recording: {str(e)}")
            return {"success": False, "message": f"Failed to start recording: {str(e)}"}
    
    def stop_recording(self) -> Dict[str, Any]:
        """Stop recording and save data"""
        if not self.is_recording:
            return {"success": False, "message": "Not recording"}
        
        try:
            self.is_recording = False
            end_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Add end metadata
            self.recording_data["metadata"]["end_time"] = end_time
            self.recording_data["metadata"]["duration"] = time.time() - self.recording_start_time
            
            # Stop stage recorder
            if STAGE_RECORDER_AVAILABLE:
                self._stop_stage_recorder()
            
            # Save recording data
            recording_file = os.path.join(
                self.recording_data["metadata"]["recording_dir"],
                "recording_data.json"
            )
            
            with open(recording_file, 'w') as f:
                json.dump(self.recording_data, f, indent=2, default=str)
            
            # Generate summary
            summary = self._generate_recording_summary()
            
            summary_file = os.path.join(
                self.recording_data["metadata"]["recording_dir"],
                "recording_summary.json"
            )
            
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            result = {
                "success": True,
                "recording_id": self.current_recording_id,
                "recording_file": recording_file,
                "summary_file": summary_file,
                "summary": summary,
                "message": f"Recording saved: {self.current_recording_id}"
            }
            
            carb.log_info(f"[Recording Manager] Stopped recording: {self.current_recording_id}")
            
            # Reset state
            self.current_recording_id = None
            self.recording_start_time = None
            
            return result
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Failed to stop recording: {str(e)}")
            return {"success": False, "message": f"Failed to stop recording: {str(e)}"}
    
    async def _recording_loop(self):
        """Main recording loop"""
        frame_count = 0
        
        while self.is_recording:
            try:
                # Check max duration
                if time.time() - self.recording_start_time > self.recording_config["max_recording_duration"]:
                    carb.log_warn("[Recording Manager] Max recording duration reached, stopping")
                    self.stop_recording()
                    break
                
                # Capture frame data
                if frame_count % (60 // self.recording_config["capture_frequency"]) == 0:
                    await self._capture_frame_data()
                
                frame_count += 1
                await asyncio.sleep(1/60)  # 60 FPS loop
                
            except Exception as e:
                carb.log_error(f"[Recording Manager] Error in recording loop: {str(e)}")
                break
    
    async def _capture_frame_data(self):
        """Capture data for current frame"""
        try:
            current_time = self._timeline.get_current_time()
            
            # Timeline data
            timeline_data = {
                "timestamp": time.time(),
                "simulation_time": current_time,
                "is_playing": self._timeline.is_playing(),
                "frame_count": len(self.recording_data["timeline_data"])
            }
            self.recording_data["timeline_data"].append(timeline_data)
            
            # Physics data
            if self.recording_config["capture_physics_data"]:
                physics_data = await self._capture_physics_data()
                self.recording_data["physics_data"].append(physics_data)
            
            # Robot data
            if self.recording_config["capture_robot_data"]:
                robot_data = await self._capture_robot_data()
                self.recording_data["robot_data"].append(robot_data)
            
            # Sensor data
            if self.recording_config["capture_sensor_data"]:
                sensor_data = await self._capture_sensor_data()
                self.recording_data["sensor_data"].append(sensor_data)
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error capturing frame data: {str(e)}")
    
    async def _capture_physics_data(self) -> Dict:
        """Capture physics simulation data"""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {}
            
            # Get physics scene info
            physics_data = {
                "timestamp": time.time(),
                "rigid_bodies": [],
                "contacts": [],
                "forces": []
            }
            
            # This would need to be expanded with actual physics data extraction
            # from the USD stage and PhysX data
            
            return physics_data
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error capturing physics data: {str(e)}")
            return {}
    
    async def _capture_robot_data(self) -> Dict:
        """Capture robot state data"""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {}
            
            robot_data = {
                "timestamp": time.time(),
                "robots": []
            }
            
            # Find robot prims and extract joint states, poses, etc.
            # This would need to be expanded based on available robot APIs
            
            return robot_data
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error capturing robot data: {str(e)}")
            return {}
    
    async def _capture_sensor_data(self) -> Dict:
        """Capture sensor data"""
        try:
            sensor_data = {
                "timestamp": time.time(),
                "cameras": [],
                "lidars": [],
                "imu": [],
                "other": []
            }
            
            # This would need to be expanded with actual sensor data extraction
            
            return sensor_data
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error capturing sensor data: {str(e)}")
            return {}
    
    def _start_stage_recorder(self, recording_dir: str):
        """Start USD stage recording"""
        try:
            if STAGE_RECORDER_AVAILABLE:
                # Configure stage recorder
                # This would need to be implemented based on available APIs
                pass
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error starting stage recorder: {str(e)}")
    
    def _stop_stage_recorder(self):
        """Stop USD stage recording"""
        try:
            if STAGE_RECORDER_AVAILABLE:
                # Stop stage recorder
                # This would need to be implemented based on available APIs
                pass
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error stopping stage recorder: {str(e)}")
    
    def _generate_recording_summary(self) -> Dict:
        """Generate recording summary"""
        try:
            timeline_data = self.recording_data.get("timeline_data", [])
            
            summary = {
                "recording_id": self.current_recording_id,
                "duration": self.recording_data["metadata"].get("duration", 0),
                "frame_count": len(timeline_data),
                "physics_events": len(self.recording_data.get("physics_data", [])),
                "robot_events": len(self.recording_data.get("robot_data", [])),
                "sensor_events": len(self.recording_data.get("sensor_data", [])),
                "simulation_time_range": {
                    "start": timeline_data[0]["simulation_time"] if timeline_data else 0,
                    "end": timeline_data[-1]["simulation_time"] if timeline_data else 0
                },
                "analysis": {
                    "avg_fps": len(timeline_data) / self.recording_data["metadata"].get("duration", 1),
                    "simulation_stability": "stable",  # Would need analysis
                    "performance_metrics": {}
                }
            }
            
            return summary
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error generating summary: {str(e)}")
            return {}
    
    def get_recordings(self) -> List[Dict]:
        """Get list of available recordings"""
        try:
            recordings = []
            
            for item in os.listdir(self.recording_path):
                recording_dir = os.path.join(self.recording_path, item)
                if os.path.isdir(recording_dir):
                    summary_file = os.path.join(recording_dir, "recording_summary.json")
                    if os.path.exists(summary_file):
                        with open(summary_file, 'r') as f:
                            summary = json.load(f)
                            recordings.append(summary)
            
            return sorted(recordings, key=lambda x: x.get("recording_id", ""), reverse=True)
            
        except Exception as e:
            carb.log_error(f"[Recording Manager] Error getting recordings: {str(e)}")
            return []
    
    def get_recording_status(self) -> Dict:
        """Get current recording status"""
        return {
            "is_recording": self.is_recording,
            "recording_id": self.current_recording_id,
            "duration": time.time() - self.recording_start_time if self.is_recording else 0,
            "recording_path": self.recording_path
        }

# Singleton instance
_recording_manager = None

def get_recording_manager() -> RecordingManager:
    """Get global recording manager instance"""
    global _recording_manager
    if _recording_manager is None:
        _recording_manager = RecordingManager()
    return _recording_manager 