/**
 * EngineGlow.jsx - Advanced engine glow with heat distortion
 */

import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function EngineGlow({ temperature, isHigh, isCritical, position }) {
  const glowRef = useRef();
  const lightRef = useRef();
  const heatRef = useRef();

  useFrame((state) => {
    const time = state.clock.elapsedTime;

    if (glowRef.current) {
      let intensity = 0.2;
      let color = '#0044ff';

      if (isCritical) {
        intensity = 2 + Math.sin(time * 8) * 1;
        color = '#ff0000';
      } else if (isHigh) {
        intensity = 1.5;
        color = '#ff6600';
      }

      glowRef.current.material.emissiveIntensity = THREE.MathUtils.lerp(
        glowRef.current.material.emissiveIntensity,
        intensity,
        0.1
      );
      glowRef.current.material.emissive.setStyle(color);
    }

    if (lightRef.current) {
      lightRef.current.intensity = isCritical ? 3 : isHigh ? 2 : 0.5;
      lightRef.current.color.setStyle(isCritical ? '#ff0000' : isHigh ? '#ff6600' : '#0044ff');
    }

    if (heatRef.current) {
      // Heat shimmer effect
      heatRef.current.rotation.y = Math.sin(time * 2) * 0.1;
      heatRef.current.material.opacity = isHigh ? 0.3 : 0;
    }
  });

  return (
    <group position={position}>
      {/* Engine block glow */}
      <mesh ref={glowRef}>
        <boxGeometry args={[1.4, 0.15, 1.0]} />
        <meshStandardMaterial
          color="#111111"
          emissive="#0044ff"
          emissiveIntensity={0.2}
          transparent
          opacity={0.7}
        />
      </mesh>

      {/* Heat distortion plane */}
      <mesh ref={heatRef} position={[0, 0.5, 0]}>
        <planeGeometry args={[1.5, 1]} />
        <meshBasicMaterial
          color="#ff6600"
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Point light */}
      <pointLight
        ref={lightRef}
        position={[0, 0.3, 0]}
        intensity={0.5}
        distance={3}
        color="#0044ff"
        decay={2}
      />

      {/* Secondary glow spots */}
      <mesh position={[-0.4, 0.1, 0.3]}>
        <sphereGeometry args={[0.1, 16, 16]} />
        <meshStandardMaterial
          emissive={isCritical ? '#ff0000' : isHigh ? '#ff6600' : '#0044ff'}
          emissiveIntensity={isCritical ? 2 : 0.5}
        />
      </mesh>
      <mesh position={[0.4, 0.1, -0.3]}>
        <sphereGeometry args={[0.1, 16, 16]} />
        <meshStandardMaterial
          emissive={isCritical ? '#ff0000' : isHigh ? '#ff6600' : '#0044ff'}
          emissiveIntensity={isCritical ? 2 : 0.5}
        />
      </mesh>
    </group>
  );
}

export default EngineGlow;