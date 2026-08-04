/**
 * BrakeLight.jsx - Advanced brake light with volumetric glow
 */

import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function BrakeLight({ position, active }) {
  const lightRef = useRef();
  const glowRef = useRef();
  const meshRef = useRef();

  useFrame((state) => {
    const intensity = active ? 3 : 0.1;
    
    if (lightRef.current) {
      lightRef.current.intensity = THREE.MathUtils.lerp(
        lightRef.current.intensity,
        intensity,
        0.15
      );
    }
    
    if (meshRef.current) {
      meshRef.current.material.emissiveIntensity = THREE.MathUtils.lerp(
        meshRef.current.material.emissiveIntensity,
        active ? 3 : 0.2,
        0.15
      );
    }

    if (glowRef.current) {
      glowRef.current.material.opacity = active ? 0.6 : 0;
      glowRef.current.scale.setScalar(active ? 1 + Math.sin(state.clock.elapsedTime * 10) * 0.1 : 1);
    }
  });

  return (
    <group position={position}>
      {/* Main light */}
      <mesh ref={meshRef}>
        <boxGeometry args={[0.35, 0.12, 0.08]} />
        <meshStandardMaterial
          color="#ff0000"
          emissive="#ff0000"
          emissiveIntensity={0.2}
          metalness={0.3}
          roughness={0.2}
        />
      </mesh>

      {/* Volumetric glow */}
      <mesh ref={glowRef} position={[0, 0, -0.1]}>
        <planeGeometry args={[0.5, 0.2]} />
        <meshBasicMaterial
          color="#ff0000"
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Light source */}
      <pointLight
        ref={lightRef}
        color="#ff0000"
        intensity={0.1}
        distance={4}
        decay={2}
        position={[0, 0, -0.2]}
      />

      {/* Light housing */}
      <mesh position={[0, 0, 0.02]}>
        <boxGeometry args={[0.38, 0.14, 0.02]} />
        <meshStandardMaterial color="#1a1a1a" metalness={0.8} roughness={0.3} />
      </mesh>
    </group>
  );
}

export default BrakeLight;