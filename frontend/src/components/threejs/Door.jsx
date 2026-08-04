/**
 * Door.jsx - Premium animated door with proper hinge mechanics
 */

import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function Door({ position, isOpen, side = 'left' }) {
  const doorRef = useRef();
  const hingeRef = useRef();
  const targetAngle = isOpen ? (side === 'left' ? -Math.PI / 2.5 : Math.PI / 2.5) : 0;

  useFrame((state, delta) => {
    if (doorRef.current) {
      // Smooth door animation with easing
      const current = doorRef.current.rotation.y;
      const diff = targetAngle - current;
      doorRef.current.rotation.y += diff * 0.08;
    }

    // Subtle door handle animation when open
    if (hingeRef.current && isOpen) {
      hingeRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 2) * 0.05;
    }
  });

  return (
    <group position={position}>
      {/* Hinge point */}
      <group ref={doorRef} position={[0, 0, 0.6]}>
        {/* Door panel */}
        <mesh position={[0, 0, -0.6]} castShadow>
          <boxGeometry args={[0.06, 0.55, 1.2]} />
          <meshStandardMaterial 
            color="#1a1a2e" 
            metalness={0.9} 
            roughness={0.15}
          />
        </mesh>

        {/* Door frame */}
        <mesh position={[0, 0.28, -0.6]}>
          <boxGeometry args={[0.07, 0.02, 1.2]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.8} roughness={0.3} />
        </mesh>
        <mesh position={[0, -0.28, -0.6]}>
          <boxGeometry args={[0.07, 0.02, 1.2]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.8} roughness={0.3} />
        </mesh>

        {/* Window */}
        <mesh position={[0, 0.25, -0.6]}>
          <boxGeometry args={[0.04, 0.25, 1.0]} />
          <meshPhysicalMaterial 
            color="#1a3a5c" 
            transparent 
            opacity={0.4} 
            metalness={0.1}
            roughness={0}
            transmission={0.9}
          />
        </mesh>

        {/* Window frame */}
        <mesh position={[0, 0.12, -0.6]}>
          <boxGeometry args={[0.05, 0.02, 1.0]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.9} roughness={0.2} />
        </mesh>

        {/* Door handle */}
        <group ref={hingeRef} position={[side === 'left' ? -0.05 : 0.05, 0, -0.6]}>
          <mesh>
            <boxGeometry args={[0.03, 0.05, 0.18]} />
            <meshStandardMaterial 
              color="#c0c0c0" 
              metalness={0.95} 
              roughness={0.1}
            />
          </mesh>
          {/* Handle accent */}
          <mesh position={[0, 0, 0.1]}>
            <boxGeometry args={[0.025, 0.04, 0.02]} />
            <meshStandardMaterial color="#2a2a2a" metalness={0.8} />
          </mesh>
        </group>

        {/* Door edge trim */}
        <mesh position={[side === 'left' ? -0.03 : 0.03, 0, -1.2]}>
          <boxGeometry args={[0.01, 0.5, 0.02]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.8} />
        </mesh>

        {/* Speaker grille */}
        <mesh position={[side === 'left' ? -0.04 : 0.04, -0.15, -0.8]}>
          <circleGeometry args={[0.06, 16]} />
          <meshStandardMaterial color="#1a1a1a" metalness={0.7} roughness={0.5} />
        </mesh>
      </group>
    </group>
  );
}

export default Door;