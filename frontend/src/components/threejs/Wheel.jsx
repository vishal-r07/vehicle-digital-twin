/**
 * Wheel.jsx - Premium realistic wheel with detailed rim
 * 
 * Features:
 * - Multi-spoke alloy rim design
 * - Tire sidewall details
 * - Brake disc visible through rim
 * - Smooth steering animation
 */

import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function Wheel({ position, rotationSpeed, steerAngle, isFront }) {
  const wheelRef = useRef();
  const steerRef = useRef();
  const targetSteer = useRef(0);

  useFrame((state, delta) => {
    if (wheelRef.current) {
      // Rotate wheel
      wheelRef.current.rotation.x += rotationSpeed * delta * 10;
    }
    
    if (steerRef.current && isFront) {
      // Smooth steering
      targetSteer.current = steerAngle;
      steerRef.current.rotation.y = THREE.MathUtils.lerp(
        steerRef.current.rotation.y,
        targetSteer.current,
        0.1
      );
    }
  });

  return (
    <group position={position}>
      {/* Steering pivot */}
      <group ref={steerRef}>
        <group rotation={[0, 0, Math.PI / 2]}>
          <group ref={wheelRef}>
          
          {/* Tire */}
          <mesh castShadow>
            <torusGeometry args={[0.35, 0.15, 24, 48]} />
            <meshStandardMaterial 
              color="#1a1a1a" 
              roughness={0.9}
              metalness={0.1}
            />
          </mesh>

          {/* Tire sidewall text effect (raised lines) */}
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <mesh 
              key={`sidewall-${i}`} 
              rotation={[0, 0, (i * Math.PI * 2) / 8]}
              position={[0, 0, 0]}
            >
              <boxGeometry args={[0.02, 0.01, 0.68]} />
              <meshStandardMaterial color="#2a2a2a" roughness={0.8} />
            </mesh>
          ))}

          {/* Rim outer ring */}
          <mesh>
            <cylinderGeometry args={[0.28, 0.28, 0.18, 32]} />
            <meshStandardMaterial 
              color="#c0c0c0" 
              metalness={0.95} 
              roughness={0.1}
            />
          </mesh>

          {/* Rim inner */}
          <mesh position={[0, 0, 0]}>
            <cylinderGeometry args={[0.22, 0.22, 0.2, 32]} />
            <meshStandardMaterial 
              color="#808080" 
              metalness={0.9} 
              roughness={0.2}
            />
          </mesh>

          {/* Rim spokes (5-spoke design) */}
          {[0, 1, 2, 3, 4].map((i) => {
            const angle = (i * Math.PI * 2) / 5;
            return (
              <group key={`spoke-${i}`} rotation={[0, 0, angle]}>
                <mesh position={[0, 0.15, 0]}>
                  <boxGeometry args={[0.06, 0.25, 0.12]} />
                  <meshStandardMaterial 
                    color="#d0d0d0" 
                    metalness={0.95} 
                    roughness={0.1}
                  />
                </mesh>
                {/* Spoke accent */}
                <mesh position={[0, 0.15, 0.07]}>
                  <boxGeometry args={[0.04, 0.2, 0.02]} />
                  <meshStandardMaterial 
                    color="#a0a0a0" 
                    metalness={0.9} 
                    roughness={0.15}
                  />
                </mesh>
              </group>
            );
          })}

          {/* Center cap */}
          <mesh position={[0, 0, 0.1]}>
            <cylinderGeometry args={[0.08, 0.08, 0.05, 16]} />
            <meshStandardMaterial 
              color="#2a2a2a" 
              metalness={0.9} 
              roughness={0.2}
            />
          </mesh>

          {/* Center logo */}
          <mesh position={[0, 0, 0.13]}>
            <circleGeometry args={[0.05, 16]} />
            <meshStandardMaterial 
              color="#00d4ff" 
              emissive="#00d4ff" 
              emissiveIntensity={0.5}
            />
          </mesh>

          {/* Brake disc (visible through spokes) */}
          <mesh position={[0, 0, -0.05]}>
            <cylinderGeometry args={[0.18, 0.18, 0.02, 32]} />
            <meshStandardMaterial 
              color="#3a3a3a" 
              metalness={0.8} 
              roughness={0.4}
            />
          </mesh>

          {/* Brake caliper */}
          <mesh position={[0.15, 0, -0.05]}>
            <boxGeometry args={[0.08, 0.12, 0.1]} />
            <meshStandardMaterial 
              color="#ff3333" 
              metalness={0.7} 
              roughness={0.3}
            />
          </mesh>
        </group>
        </group>
      </group>
    </group>
  );
}

export default Wheel;