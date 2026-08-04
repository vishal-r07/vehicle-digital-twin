/**
 * FuelIndicator3D.jsx - Premium 3D fuel gauge
 */

import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function FuelIndicator3D({ fuel, isLow, position }) {
  const meshRef = useRef();
  const glowRef = useRef();

  useFrame((state) => {
    if (meshRef.current) {
      if (isLow) {
        const blink = Math.sin(state.clock.elapsedTime * 4) > 0 ? 1 : 0.3;
        meshRef.current.material.emissiveIntensity = blink;
        meshRef.current.material.color.setStyle('#ff6b35');
      } else {
        meshRef.current.material.emissiveIntensity = 0.5;
        meshRef.current.material.color.setStyle('#00d4ff');
      }
    }

    if (glowRef.current) {
      glowRef.current.material.opacity = isLow ? 0.4 : 0.2;
    }
  });

  const fillHeight = (fuel / 100) * 0.4;
  const isEmpty = fuel < 5;

  return (
    <group position={position}>
      {/* Fuel tank outline */}
      <mesh>
        <boxGeometry args={[0.18, 0.4, 0.18]} />
        <meshStandardMaterial 
          color="#1a1a1a" 
          metalness={0.8} 
          roughness={0.3}
          transparent 
          opacity={0.6} 
        />
      </mesh>

      {/* Tank frame */}
      <mesh position={[0, 0.21, 0]}>
        <boxGeometry args={[0.2, 0.02, 0.2]} />
        <meshStandardMaterial color="#0a0a0a" metalness={0.9} />
      </mesh>
      <mesh position={[0, -0.21, 0]}>
        <boxGeometry args={[0.2, 0.02, 0.2]} />
        <meshStandardMaterial color="#0a0a0a" metalness={0.9} />
      </mesh>

      {/* Fuel level */}
      <mesh ref={meshRef} position={[0, -0.2 + fillHeight / 2, 0]}>
        <boxGeometry args={[0.14, fillHeight, 0.14]} />
        <meshStandardMaterial
          color={isLow ? '#ff6b35' : '#00d4ff'}
          emissive={isLow ? '#ff6b35' : '#00d4ff'}
          emissiveIntensity={0.5}
          transparent
          opacity={0.9}
        />
      </mesh>

      {/* Glow effect */}
      <mesh ref={glowRef} position={[0, -0.2 + fillHeight / 2, 0.1]}>
        <planeGeometry args={[0.2, fillHeight]} />
        <meshBasicMaterial
          color={isLow ? '#ff6b35' : '#00d4ff'}
          transparent
          opacity={0.2}
          blending={THREE.AdditiveBlending}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Fuel cap */}
      <mesh position={[0.1, 0.15, 0.1]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.03, 0.03, 0.02, 16]} />
        <meshStandardMaterial color="#2a2a2a" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Level markers */}
      {[0, 0.25, 0.5, 0.75, 1].map((level, i) => (
        <mesh key={i} position={[0.1, -0.2 + level * 0.4, 0.1]}>
          <boxGeometry args={[0.01, 0.005, 0.02]} />
          <meshStandardMaterial color="#c0c0c0" metalness={0.9} />
        </mesh>
      ))}
    </group>
  );
}

export default FuelIndicator3D;