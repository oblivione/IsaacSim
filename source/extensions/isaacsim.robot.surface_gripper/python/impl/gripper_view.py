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

from __future__ import annotations

import isaacsim.core.experimental.utils.ops as ops_utils
import isaacsim.robot.surface_gripper._surface_gripper as surface_gripper
import numpy as np
import warp as wp
from isaacsim.core.experimental.prims import XformPrim
from usd.schema.isaac import robot_schema


class GripperView(XformPrim):
    """Provides high level functions to deal with batched data from surface gripper

    Args:
        paths: Prim paths regex to encapsulate all prims that match it. E.g.: "/World/Env[1-5]/Gripper" will match
               /World/Env1/Gripper, /World/Env2/Gripper..etc. Additionally a list of regex can be provided.
        max_grip_distance: Maximum distance for which the surface gripper can gripped an object. Shape is (N).
                           Defaults to None, which means left unchanged.
        coaxial_force_limit: Maximum coaxial force that the surface gripper can withstand without dropping the gripped object. Shape is (N).
                             Defaults to None, which means left unchanged.
        shear_force_limit: Maximum shear force that the surface gripper can withstand without dropping the gripped object. Shape is (N).
                           Defaults to None, which means left unchanged.
        retry_interval: Indicates the duration for which the surface gripper is attempting to grip an object.
                        Defaults to None, which means left unchanged.
        positions: Default positions in the world frame of the prim. Shape is (N, 3).
                   Defaults to None, which means left unchanged.
        translations: Default translations in the local frame of the prims (with respect to its parent prims). shape is (N, 3).
                      Defaults to None, which means left unchanged.
        orientations: Default quaternion orientations in the world/ local frame of the prim (depends if translation
                      or position is specified). Quaternion is scalar-first (w, x, y, z). Shape is (N, 4).
                      Defaults to None, which means left unchanged.
        scales: Local scales to be applied to the prim's dimensions. Shape is (N, 3).
                Defaults to None, which means left unchanged.
        reset_xform_properties: True if the prims don't have the right set of xform properties (i.e: translate,
                                orient and scale) ONLY and in that order. Set this parameter to False if the object
                                were cloned using using the cloner api in isaacsim.core.cloner. Defaults to True.

    Raises:
        Exception: if translations and positions defined at the same time.
        Exception: No prim was matched using the prim_paths_expr provided.
    """

    def __init__(
        self,
        paths: str = None,
        max_grip_distance: np.ndarray | wp.array | None = None,
        coaxial_force_limit: np.ndarray | wp.array | None = None,
        shear_force_limit: np.ndarray | wp.array | None = None,
        retry_interval: np.ndarray | wp.array | None = None,
        positions: np.ndarray | wp.array | None = None,
        translations: np.ndarray | wp.array | None = None,
        orientations: np.ndarray | wp.array | None = None,
        scales: np.ndarray | wp.array | None = None,
        reset_xform_op_properties: bool = True,
    ):
        XformPrim.__init__(
            self,
            paths=paths,
            positions=positions,
            translations=translations,
            orientations=orientations,
            scales=scales,
            reset_xform_op_properties=reset_xform_op_properties,
        )
        self.count = len(self)
        self.surface_gripper_interface = surface_gripper.acquire_surface_gripper_interface()
        self.set_surface_gripper_properties(max_grip_distance, coaxial_force_limit, shear_force_limit, retry_interval)

    def __del__(self):
        XformPrim.__del__(self)

    def get_surface_gripper_status(self, indices: list | np.ndarray | wp.array | None = None) -> list[str]:
        """Get the status for the surface grippers.

        Args:
            indices: Specific surface gripper to update. Shape (M,). Where M <= size of the encapsulated prims in the view.
                     Defaults to None (i.e: all prims in the view).

        Returns:
            list[str]: Status of the surface grippers ("Open", "Closing", or "Closed"). Shape (M,).
        """
        gripper_status = []
        indices = ops_utils.resolve_indices(indices, count=self.count, device="cpu").numpy()
        for i in indices:
            gripper_status.append(self.surface_gripper_interface.get_gripper_status(self.prims[i].GetPath().pathString))

        return gripper_status

    def get_surface_gripper_properties(
        self, indices: list | np.ndarray | wp.array | None = None
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        """Get the properties for the surface grippers.

        Args:
            indices: Specific surface gripper to update. Shape (M,). Where M <= size of the encapsulated prims in the view.
                     Defaults to None (i.e: all prims in the view).

        Returns:
            tuple[list[float], list[float], list[float], list[float]]: First index is maximum grip distance. Shape (M,).
                                                                       Second index is coaxial force limit. Shape (M,).
                                                                       Third index is shear force limit. Shape (M,).
                                                                       Fourth index is the retry interval. Shape (M,).
        """
        max_grip_distance = []
        coaxial_force_limit = []
        shear_force_limit = []
        retry_interval = []

        indices = ops_utils.resolve_indices(indices, count=self.count, device="cpu").numpy()
        for i in indices:
            max_grip_distance.append(self.prims[i].GetAttribute(robot_schema.Attributes.MAX_GRIP_DISTANCE.name).Get())
            coaxial_force_limit.append(
                self.prims[i].GetAttribute(robot_schema.Attributes.COAXIAL_FORCE_LIMIT.name).Get()
            )
            shear_force_limit.append(self.prims[i].GetAttribute(robot_schema.Attributes.SHEAR_FORCE_LIMIT.name).Get())
            retry_interval.append(self.prims[i].GetAttribute(robot_schema.Attributes.RETRY_INTERVAL.name).Get())

        return max_grip_distance, coaxial_force_limit, shear_force_limit, retry_interval

    def apply_gripper_action(
        self,
        values: list[float],
        indices: list | np.ndarray | wp.array | None = None,
    ) -> None:
        """Set up the status for the surface grippers.

        Args:
            values: New status of the surface gripper. Shape (N,). Where N is the number of encapsulated prims in the view.
            indices: Specific surface gripper to update. Shape (M,). Where M <= size of the encapsulated prims in the view.
                     Defaults to None (i.e: all prims in the view).

        Raises:
            Exception: If the length of values does not match the number of encapsulated prims in the view.
            Exception: If a value in indices is larger then the number of encapsulated prims in the view.
        """
        # Ensure length of values matches number of gripper
        if self.count != len(values):
            raise ValueError("Length of values must match number of grippers")

        indices = ops_utils.resolve_indices(indices, count=self.count, device="cpu").numpy()
        for i in indices:
            # Ensure indice has a matching values
            if i >= len(values):
                raise ValueError("Indices should be compatible with length of values")

            self.surface_gripper_interface.set_gripper_action(self.prims[i].GetPath().pathString, values[i])

        return

    def set_surface_gripper_properties(
        self,
        max_grip_distance: list[float] | None = None,
        coaxial_force_limit: list[float] | None = None,
        shear_force_limit: list[float] | None = None,
        retry_interval: list[float] | None = None,
        indices: list | np.ndarray | wp.array | None = None,
    ) -> None:
        """Set up the properties for the surface grippers.

        Args:
            max_grip_distance: New maximum grip distance of the surface gripper. Shape (N,). Where N is the number of encapsulated prims in the view.
                               Defaults to None, which means left unchanged.
            coaxial_force_limit: New coaxial force limit of the surface gripper. Shape (N,). Where N is the number of encapsulated prims in the view.
                                 Defaults to None, which means left unchanged.
            shear_force_limit: New shear force limit of the surface gripper. Shape (N,). Where N is the number of encapsulated prims in the view.
                               Defaults to None, which means left unchanged.
            retry_interval: New retry interval of the surface gripper. Shape (N,). Where N is the number of encapsulated prims in the view.
                            Defaults to None, which means left unchanged.
            indices: Specific surface gripper to update. Shape (M,). Where M <= size of the encapsulated prims in the view.
                     Defaults to None (i.e: all prims in the view).

        Raises:
            Exception: If the length of any properties does not match the number of encapsulated prims in the view.
            Exception: If a value in indices is larger then the number of encapsulated prims in the view.
        """
        indices = ops_utils.resolve_indices(indices, count=self.count, device="cpu").numpy()
        # Setup max grip distance if provided
        if max_grip_distance is not None:
            # Ensure length of max_grip_distance matches number of gripper
            if self.count != len(max_grip_distance):
                raise ValueError("Length of max_grip_distance must match number of grippers")

            for i in indices:
                # Ensure indice has a matching values
                if i >= len(max_grip_distance):
                    raise ValueError("Indices should be compatible with length of max_grip_distance")

                self.prims[i].GetAttribute(robot_schema.Attributes.MAX_GRIP_DISTANCE.name).Set(max_grip_distance[i])

        # Setup coaxial force limit if provided
        if coaxial_force_limit is not None:
            # Ensure length of coaxial_force_limit matches number of gripper
            if self.count != len(coaxial_force_limit):
                raise ValueError("Length of coaxial_force_limit must match number of grippers")

            for i in indices:
                # Ensure indice has a matching values
                if i >= len(coaxial_force_limit):
                    raise ValueError("Indices should be compatible with length of coaxial_force_limit")

                self.prims[i].GetAttribute(robot_schema.Attributes.COAXIAL_FORCE_LIMIT.name).Set(coaxial_force_limit[i])

        # Setup shear force limit if provided
        if shear_force_limit is not None:
            # Ensure length of shear_force_limit matches number of gripper
            if self.count != len(shear_force_limit):
                raise ValueError("Length of shear_force_limit must match number of grippers")

            for i in indices:
                # Ensure indice has a matching values
                if i >= len(shear_force_limit):
                    raise ValueError("Indices should be compatible with length of shear_force_limit")

                self.prims[i].GetAttribute(robot_schema.Attributes.SHEAR_FORCE_LIMIT.name).Set(shear_force_limit[i])

        # Setup retry interval if provided
        if retry_interval is not None:
            # Ensure length of retry_interval matches number of gripper
            if self.count != len(retry_interval):
                raise ValueError("Length of retry_interval must match number of grippers")

            for i in indices:
                # Ensure indice has a matching values
                if i >= len(retry_interval):
                    raise ValueError("Indices should be compatible with length of retry_interval")

                self.prims[i].GetAttribute(robot_schema.Attributes.RETRY_INTERVAL.name).Set(retry_interval[i])

        return
