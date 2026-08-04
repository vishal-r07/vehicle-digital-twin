/**
 * CameraController.jsx - Cinematic camera system
 * 
 * Features:
 * - Smooth camera transitions
 * - Dynamic camera positioning based on vehicle state
 * - Chase cam mode
 * - Orbit mode with auto-rotation
 */

import { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

function CameraController({ data, isInteractingRef }) {
  const { camera } = useThree();
  const targetPosition = useRef(new THREE.Vector3(6, 3, 6));
  const targetLookAt = useRef(new THREE.Vector3(0, 0.5, 0));
  const currentPosition = useRef(new THREE.Vector3(6, 3, 6));

  const d = data || { speed: 0, steering: 0, speedNorm: 0, steeringNorm: 0 };

  useFrame((state, delta) => {
    if (isInteractingRef && isInteractingRef.current) {
      currentPosition.current.copy(camera.position);
      return;
    }
    
    // Calculate dynamic camera position based on vehicle state
    const speed = d.speed || 0;
    const steering = d.steeringNorm || 0;

    // Base camera position (chase cam)
    const distance = 6 - speed * 0.01; // Closer at high speed
    const height = 2.5 + speed * 0.005; // Higher at high speed
    const angle = Math.PI / 4 + steering * 0.1; // Slight angle adjustment

    targetPosition.current.set(
      Math.cos(angle) * distance,
      height,
      Math.sin(angle) * distance
    );

    // Smooth camera movement
    currentPosition.current.lerp(targetPosition.current, 0.02);
    camera.position.copy(currentPosition.current);

    // Look at vehicle center
    targetLookAt.current.set(0, 0.5, 0);
    camera.lookAt(targetLookAt.current);
  });

  return null;
}

export default CameraController;