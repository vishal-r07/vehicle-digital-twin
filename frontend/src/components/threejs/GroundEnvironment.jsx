/**
 * GroundEnvironment.jsx - Premium ground plane with reflections
 * 
 * Features:
 * - Reflective surface
 * - Grid pattern
 * - Atmospheric fog
 */

import { useRef } from 'react';
import { MeshReflectorMaterial } from '@react-three/drei';
import * as THREE from 'three';

function GroundEnvironment() {
  return (
    <group>
      {/* Reflective ground */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]} receiveShadow>
        <planeGeometry args={[50, 50]} />
        <MeshReflectorMaterial
          blur={[300, 100]}
          resolution={1024}
          mixBlur={1}
          mixStrength={40}
          roughness={1}
          depthScale={1.2}
          minDepthThreshold={0.4}
          maxDepthThreshold={1.4}
          color="#0a0e17"
          metalness={0.5}
          mirror={0.5}
        />
      </mesh>

      {/* Grid overlay */}
      <gridHelper
        args={[50, 50, '#1e2a42', '#1a2238']}
        position={[0, -0.49, 0]}
      />

      {/* Circular platform */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.48, 0]}>
        <ringGeometry args={[3, 3.1, 64]} />
        <meshStandardMaterial
          color="#00d4ff"
          emissive="#00d4ff"
          emissiveIntensity={0.5}
          transparent
          opacity={0.6}
        />
      </mesh>

      {/* Inner ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.48, 0]}>
        <ringGeometry args={[2.5, 2.55, 64]} />
        <meshStandardMaterial
          color="#ff6b35"
          emissive="#ff6b35"
          emissiveIntensity={0.3}
          transparent
          opacity={0.4}
        />
      </mesh>
    </group>
  );
}

export default GroundEnvironment;