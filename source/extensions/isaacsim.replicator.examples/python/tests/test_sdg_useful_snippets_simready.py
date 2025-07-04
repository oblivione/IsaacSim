# SPDX-FileCopyrightText: Copyright (c) 2024-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import omni.kit
import omni.usd

from .common import validate_folder_contents


class TestSDGUsefulSnippetsSimready(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        await omni.kit.app.get_app().next_update_async()
        omni.usd.get_context().new_stage()
        await omni.kit.app.get_app().next_update_async()

    async def tearDown(self):
        omni.usd.get_context().close_stage()
        await omni.kit.app.get_app().next_update_async()
        # In some cases the test will end before the asset is loaded, in this case wait for assets to load
        while omni.usd.get_context().get_stage_loading_status()[2] > 0:
            await omni.kit.app.get_app().next_update_async()

    async def test_sdg_snippet_simready_assets(self):
        import asyncio
        import os
        import random

        import omni.kit.app
        import omni.replicator.core as rep
        import omni.timeline
        import omni.usd
        from isaacsim.core.utils.semantics import upgrade_prim_semantics_to_labels
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

        # Make sure the simready explorer extension is enabled
        ext_manager = omni.kit.app.get_app().get_extension_manager()
        if not ext_manager.is_extension_enabled("omni.simready.explorer"):
            ext_manager.set_extension_enabled_immediate("omni.simready.explorer", True)
        import omni.simready.explorer as sre

        def enable_simready_explorer():
            if sre.get_instance().browser_model is None:
                import omni.kit.actions.core as actions

                actions.execute_action("omni.simready.explorer", "toggle_window")

        async def search_assets_async():
            print(f"Searching for simready assets...")
            tables = await sre.find_assets(["table", "furniture"])
            plates = await sre.find_assets(["plate"])
            bowls = await sre.find_assets(["bowl"])
            dishes = plates + bowls
            fruits = await sre.find_assets(["fruit"])
            vegetables = await sre.find_assets(["vegetable"])
            items = fruits + vegetables
            return tables, dishes, items

        async def run_simready_randomization_async(stage, camera_prim, render_product, tables, dishes, items):
            print(f"Creating new temp layer for randomizing the scene...")
            simready_temp_layer = Sdf.Layer.CreateAnonymous("TempSimreadyLayer")
            session = stage.GetSessionLayer()
            session.subLayerPaths.append(simready_temp_layer.identifier)

            with Usd.EditContext(stage, simready_temp_layer):
                # Load the simready assets with rigid body properties
                variants = {"PhysicsVariant": "RigidBody"}

                # Choose a random table from the list of tables and add it to the stage with physics
                table_asset = random.choice(tables)
                print(f"\tAdding table '{table_asset.name}' with colliders and disabled rigid body properties")
                _, table_prim_path = sre.add_asset_to_stage(table_asset.main_url, variants=variants, payload=True)
                table_prim = stage.GetPrimAtPath(table_prim_path)
                upgrade_prim_semantics_to_labels(table_prim)
                if not table_prim.HasAPI(UsdPhysics.RigidBodyAPI):
                    rigid_body_api = UsdPhysics.RigidBodyAPI.Apply(table_prim)
                else:
                    rigid_body_api = UsdPhysics.RigidBodyAPI(table_prim)
                rigid_body_api.CreateRigidBodyEnabledAttr(False)

                # Compute the height of the table from its bounding box
                bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), includedPurposes=[UsdGeom.Tokens.default_])
                table_bbox = bbox_cache.ComputeWorldBound(table_prim)
                table_size = table_bbox.GetRange().GetSize()

                # Choose one random plate from the list of plates
                dish_asset = random.choice(dishes)
                _, dish_prim_path = sre.add_asset_to_stage(dish_asset.main_url, variants=variants, payload=True)

                dish_prim = stage.GetPrimAtPath(dish_prim_path)
                upgrade_prim_semantics_to_labels(dish_prim)

                # Compute the height of the plate from its bounding box
                dish_bbox = bbox_cache.ComputeWorldBound(dish_prim)
                dish_size = dish_bbox.GetRange().GetSize()

                # Get a random position for the plate near the center of the table
                placement_reduction = 0.75
                x_range = (table_size[0] - dish_size[0]) / 2 * placement_reduction
                y_range = (table_size[1] - dish_size[1]) / 2 * placement_reduction
                dish_x = random.uniform(-x_range, x_range)
                dish_y = random.uniform(-y_range, y_range)
                dish_z = table_size[2] + dish_size[2] / 2

                # Move the plate to the random position on the table
                dish_location = Gf.Vec3f(dish_x, dish_y, dish_z)
                dish_prim.GetAttribute("xformOp:translate").Set(dish_location)
                print(f"\tAdded '{dish_asset.name}' at: {dish_location}")

                # Spawn a random number of items above the plate
                num_items = random.randint(2, 4)
                print(f"\tAdding {num_items} items above the plate '{dish_asset.name}':")
                item_prims = []
                for _ in range(num_items):
                    item_asset = random.choice(items)
                    _, item_prim_path = sre.add_asset_to_stage(item_asset.main_url, variants=variants, payload=True)
                    item_prim = stage.GetPrimAtPath(item_prim_path)
                    upgrade_prim_semantics_to_labels(item_prim)
                    item_prims.append(item_prim)

                current_z = dish_z
                xy_offset = dish_size[0] / 4
                for item_prim in item_prims:
                    item_bbox = bbox_cache.ComputeWorldBound(item_prim)
                    item_size = item_bbox.GetRange().GetSize()
                    item_x = dish_x + random.uniform(-xy_offset, xy_offset)
                    item_y = dish_y + random.uniform(-xy_offset, xy_offset)
                    item_z = current_z + item_size[2] / 2
                    item_location = Gf.Vec3f(item_x, item_y, item_z)
                    item_prim.GetAttribute("xformOp:translate").Set(item_location)
                    print(f"\t\t'{item_prim.GetName()}' at: {item_location}")
                    current_z += item_size[2]

                num_sim_steps = 25
                print(f"\tRunning the simulation for {num_sim_steps} steps for the items to settle...")
                timeline = omni.timeline.get_timeline_interface()
                timeline.play()
                for _ in range(num_sim_steps):
                    await omni.kit.app.get_app().next_update_async()
                print(f"\tPausing the simulation")
                timeline.pause()

                print(f"\tMoving the camera above the scene to capture the scene...")
                camera_prim.GetAttribute("xformOp:translate").Set(Gf.Vec3f(dish_x, dish_y, dish_z + 2))
                render_product.hydra_texture.set_updates_enabled(True)
                await rep.orchestrator.step_async(delta_time=0.0, rt_subframes=16)
                render_product.hydra_texture.set_updates_enabled(False)
                await omni.kit.app.get_app().next_update_async()

            print("\tStopping the timeline")
            timeline.stop()
            await omni.kit.app.get_app().next_update_async()

            print(f"\tRemoving the temp layer")
            session.subLayerPaths.remove(simready_temp_layer.identifier)
            simready_temp_layer = None

        async def run_simready_randomizations_async(num_scenarios):
            await omni.usd.get_context().new_stage_async()
            stage = omni.usd.get_context().get_stage()
            rep.orchestrator.set_capture_on_play(False)
            random.seed(15)

            # Add lights to the scene
            dome_light = stage.DefinePrim("/World/DomeLight", "DomeLight")
            dome_light.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(500.0)
            distant_light = stage.DefinePrim("/World/DistantLight", "DistantLight")
            if not distant_light.GetAttribute("xformOp:rotateXYZ"):
                UsdGeom.Xformable(distant_light).AddRotateXYZOp()
            distant_light.GetAttribute("xformOp:rotateXYZ").Set((-75, 0, 0))
            distant_light.CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(2500)

            # Simready explorer window needs to be created for the search to work
            enable_simready_explorer()

            # Search for the simready assets
            tables, dishes, items = await search_assets_async()
            print(f"\tFound {len(tables)} tables, {len(dishes)} dishes, {len(items)} items")

            # Create the writer and the render product for capturing the scene
            output_dir = os.path.join(os.getcwd(), "_out_simready_assets")
            print(f"\tInitializing writer, output directory: {output_dir}...")
            writer = rep.writers.get("BasicWriter")
            writer.initialize(output_dir=output_dir, rgb=True)

            # Disable the render by default, enable it when capturing the scene
            camera_prim = stage.DefinePrim("/World/SceneCamera", "Camera")
            UsdGeom.Xformable(camera_prim).AddTranslateOp()
            rp = rep.create.render_product(camera_prim.GetPath(), (512, 512))
            rp.hydra_texture.set_updates_enabled(False)
            writer.attach(rp)

            for i in range(num_scenarios):
                print(f"Running simready randomization scenario {i}..")
                await run_simready_randomization_async(
                    stage=stage, camera_prim=camera_prim, render_product=rp, tables=tables, dishes=dishes, items=items
                )

            print("Waiting for the data collection to complete")
            await rep.orchestrator.wait_until_complete_async()
            print("Detaching writer and destroying render product")
            writer.detach()
            rp.destroy()

        num_scenarios = 2
        print(f"Running {num_scenarios} simready randomization scenarios...")
        await run_simready_randomizations_async(num_scenarios)

        out_dir = os.path.join(os.getcwd(), "_out_simready_assets")
        folder_contents_success = validate_folder_contents(path=out_dir, expected_counts={"png": num_scenarios})
        self.assertTrue(folder_contents_success, f"Output directory contents validation failed for {out_dir}")
