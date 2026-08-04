/**
 * VehicleModel.jsx - Premium 3D vehicle with realistic proportions
 * 
 * Features:
 * - Detailed body geometry with curves
 * - Realistic materials (metallic paint, chrome, glass)
 * - Dynamic animations (suspension, body roll, steering)
 * - Working lights with volumetric effects
 * - Particle effects (exhaust, tire smoke)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import Wheel from './Wheel';
import BrakeLight from './BrakeLight';
import EngineGlow from './EngineGlow';
import Door from './Door';
import ParticleEffects from './ParticleEffects';

function VehicleModel({ data }) {
  const groupRef = useRef();
  const bodyRef = useRef();
  const suspensionRef = useRef();
  
  const d = data || {
    speed: 0, rpm: 0, fuel: 100, temp: 25, battery: 12.6,
    steering: 0, brake: 0, accelerator: 0, gear: 'P', door: 'Closed',
    speedNorm: 0, steeringNorm: 0, isTempHigh: false, isTempCritical: false,
    isFuelLow: false, isBraking: false,
  };

  // Calculations
  const wheelSpeed = useMemo(() => d.speed * 0.05, [d.speed]);
  const steerAngle = useMemo(() => d.steeringNorm * 0.6, [d.steeringNorm]);
  const bodyLean = useMemo(() => d.steeringNorm * 0.03, [d.steeringNorm]);
  const brakeDive = useMemo(() => d.isBraking ? -0.02 : 0, [d.isBraking]);
  const accelLift = useMemo(() => d.accelerator > 50 ? 0.01 : 0, [d.accelerator]);

  // Animation loop
  useFrame((state, delta) => {
    if (bodyRef.current) {
      // Body lean on steering
      bodyRef.current.rotation.z = THREE.MathUtils.lerp(
        bodyRef.current.rotation.z,
        bodyLean,
        0.05
      );

      // Brake dive / acceleration lift
      const targetY = 0.5 + brakeDive + accelLift;
      bodyRef.current.position.y = THREE.MathUtils.lerp(
        bodyRef.current.position.y,
        targetY,
        0.1
      );

      // Subtle vibration from engine
      const vibration = (d.rpm / 8000) * 0.002;
      bodyRef.current.position.x = Math.sin(state.clock.elapsedTime * 25) * vibration;
    }

    if (groupRef.current) {
      // Gentle hover effect
      groupRef.current.position.y = Math.sin(state.clock.elapsedTime * 0.5) * 0.01;
    }
  });

  return (
    <group ref={groupRef} position={[0, 0, 0]}>
      <group ref={bodyRef}>
        {/* Main Body - Lower */}
        <mesh castShadow receiveShadow position={[0, 0, 0]}>
          <boxGeometry args={[2.1, 0.6, 4.5]} />
          <meshStandardMaterial 
            color="#1a1a2e" 
            metalness={0.9} 
            roughness={0.15}
            envMapIntensity={1.5}
          />
        </mesh>

        {/* Body Curves - Front Fenders */}
        <mesh castShadow position={[-1.05, 0.1, 1.5]}>
          <sphereGeometry args={[0.5, 32, 32, 0, Math.PI, 0, Math.PI]} />
          <meshStandardMaterial 
            color="#1a1a2e" 
            metalness={0.9} 
            roughness={0.15}
          />
        </mesh>
        <mesh castShadow position={[1.05, 0.1, 1.5]}>
          <sphereGeometry args={[0.5, 32, 32, 0, Math.PI, 0, Math.PI]} />
          <meshStandardMaterial 
            color="#1a1a2e" 
            metalness={0.9} 
            roughness={0.15}
          />
        </mesh>

        {/* Cabin */}
        <mesh castShadow position={[0, 0.5, -0.3]}>
          <boxGeometry args={[1.8, 0.6, 2.2]} />
          <meshStandardMaterial 
            color="#0f0f23" 
            metalness={0.95} 
            roughness={0.1}
          />
        </mesh>

        {/* Roof */}
        <mesh castShadow position={[0, 0.85, -0.3]}>
          <boxGeometry args={[1.7, 0.1, 2.1]} />
          <meshStandardMaterial 
            color="#0a0a1a" 
            metalness={0.9} 
            roughness={0.2}
          />
        </mesh>

        {/* Windshield */}
        <mesh position={[0, 0.55, 0.75]} rotation={[-0.4, 0, 0]}>
          <planeGeometry args={[1.6, 0.65]} />
          <meshPhysicalMaterial 
            color="#1a3a5c"
            metalness={0.1}
            roughness={0}
            transmission={0.9}
            transparent
            opacity={0.4}
            envMapIntensity={2}
          />
        </mesh>

        {/* Rear Window */}
        <mesh position={[0, 0.55, -1.35]} rotation={[0.3, Math.PI, 0]}>
          <planeGeometry args={[1.5, 0.55]} />
          <meshPhysicalMaterial 
            color="#1a3a5c"
            metalness={0.1}
            roughness={0}
            transmission={0.9}
            transparent
            opacity={0.4}
          />
        </mesh>

        {/* Side Windows */}
        <mesh position={[-0.91, 0.55, -0.3]} rotation={[0, -Math.PI / 2, 0]}>
          <planeGeometry args={[2.0, 0.5]} />
          <meshPhysicalMaterial 
            color="#1a3a5c"
            metalness={0.1}
            roughness={0}
            transmission={0.9}
            transparent
            opacity={0.3}
          />
        </mesh>
        <mesh position={[0.91, 0.55, -0.3]} rotation={[0, Math.PI / 2, 0]}>
          <planeGeometry args={[2.0, 0.5]} />
          <meshPhysicalMaterial 
            color="#1a3a5c"
            metalness={0.1}
            roughness={0}
            transmission={0.9}
            transparent
            opacity={0.3}
          />
        </mesh>

        {/* Hood */}
        <mesh castShadow position={[0, 0.35, 1.75]}>
          <boxGeometry args={[1.9, 0.08, 1.3]} />
          <meshStandardMaterial 
            color="#1a1a2e" 
            metalness={0.9} 
            roughness={0.15}
          />
        </mesh>

        {/* Hood Lines */}
        <mesh position={[-0.4, 0.4, 1.75]}>
          <boxGeometry args={[0.02, 0.01, 1.2]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.8} />
        </mesh>
        <mesh position={[0.4, 0.4, 1.75]}>
          <boxGeometry args={[0.02, 0.01, 1.2]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.8} />
        </mesh>

        {/* Trunk */}
        <mesh castShadow position={[0, 0.35, -1.9]}>
          <boxGeometry args={[1.9, 0.08, 0.8]} />
          <meshStandardMaterial 
            color="#1a1a2e" 
            metalness={0.9} 
            roughness={0.15}
          />
        </mesh>

        {/* Front Bumper */}
        <mesh castShadow position={[0, -0.1, 2.25]}>
          <boxGeometry args={[2.0, 0.3, 0.2]} />
          <meshStandardMaterial 
            color="#0a0a0a" 
            metalness={0.7} 
            roughness={0.3}
          />
        </mesh>

        {/* Grille */}
        <mesh position={[0, -0.05, 2.3]}>
          <boxGeometry args={[1.2, 0.2, 0.05]} />
          <meshStandardMaterial 
            color="#1a1a1a" 
            metalness={0.9} 
            roughness={0.2}
          />
        </mesh>

        {/* Chrome Grille Accent */}
        <mesh position={[0, 0.05, 2.32]}>
          <boxGeometry args={[1.3, 0.02, 0.02]} />
          <meshStandardMaterial 
            color="#e0e0e0" 
            metalness={1} 
            roughness={0.1}
          />
        </mesh>

        {/* Headlights */}
        <group position={[-0.75, 0, 2.2]}>
          <mesh>
            <boxGeometry args={[0.35, 0.2, 0.15]} />
            <meshPhysicalMaterial 
              color="#ffffff"
              emissive="#ffffff"
              emissiveIntensity={0.8}
              metalness={0.3}
              roughness={0}
              transmission={0.5}
              transparent
              opacity={0.9}
            />
          </mesh>
          <pointLight
            position={[0, 0, 0.2]}
            intensity={2}
            distance={8}
            angle={0.4}
            penumbra={0.5}
            color="#fff5e6"
          />
        </group>

        <group position={[0.75, 0, 2.2]}>
          <mesh>
            <boxGeometry args={[0.35, 0.2, 0.15]} />
            <meshPhysicalMaterial 
              color="#ffffff"
              emissive="#ffffff"
              emissiveIntensity={0.8}
              metalness={0.3}
              roughness={0}
              transmission={0.5}
              transparent
              opacity={0.9}
            />
          </mesh>
          <pointLight
            position={[0, 0, 0.2]}
            intensity={2}
            distance={8}
            angle={0.4}
            penumbra={0.5}
            color="#fff5e6"
          />
        </group>

        {/* DRL (Daytime Running Lights) */}
        <mesh position={[-0.75, -0.15, 2.28]}>
          <boxGeometry args={[0.3, 0.03, 0.02]} />
          <meshStandardMaterial 
            color="#00d4ff"
            emissive="#00d4ff"
            emissiveIntensity={1.5}
          />
        </mesh>
        <mesh position={[0.75, -0.15, 2.28]}>
          <boxGeometry args={[0.3, 0.03, 0.02]} />
          <meshStandardMaterial 
            color="#00d4ff"
            emissive="#00d4ff"
            emissiveIntensity={1.5}
          />
        </mesh>

        {/* Engine Glow */}
        <EngineGlow
          temperature={d.temp}
          isHigh={d.isTempHigh}
          isCritical={d.isTempCritical}
          position={[0, 0.15, 1.5]}
        />

        {/* Brake Lights */}
        <BrakeLight position={[-0.7, 0.1, -2.25]} active={d.isBraking} />
        <BrakeLight position={[0.7, 0.1, -2.25]} active={d.isBraking} />

        {/* Rear Bumper */}
        <mesh castShadow position={[0, -0.1, -2.25]}>
          <boxGeometry args={[2.0, 0.3, 0.2]} />
          <meshStandardMaterial 
            color="#0a0a0a" 
            metalness={0.7} 
            roughness={0.3}
          />
        </mesh>

        {/* Exhaust Pipes */}
        <mesh position={[-0.5, -0.2, -2.3]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.06, 0.06, 0.15, 16]} />
          <meshStandardMaterial 
            color="#2a2a2a" 
            metalness={0.9} 
            roughness={0.2}
          />
        </mesh>
        <mesh position={[0.5, -0.2, -2.3]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.06, 0.06, 0.15, 16]} />
          <meshStandardMaterial 
            color="#2a2a2a" 
            metalness={0.9} 
            roughness={0.2}
          />
        </mesh>

        {/* Doors */}
        <Door
          position={[-1.06, 0.15, -0.3]}
          isOpen={d.door.includes('FL') || d.door === 'All Open'}
          side="left"
        />
        <Door
          position={[1.06, 0.15, -0.3]}
          isOpen={d.door.includes('FR') || d.door === 'All Open'}
          side="right"
        />

        {/* Side Mirrors */}
        <mesh position={[-1.1, 0.5, 0.5]}>
          <boxGeometry args={[0.15, 0.1, 0.1]} />
          <meshStandardMaterial color="#1a1a2e" metalness={0.9} roughness={0.15} />
        </mesh>
        <mesh position={[1.1, 0.5, 0.5]}>
          <boxGeometry args={[0.15, 0.1, 0.1]} />
          <meshStandardMaterial color="#1a1a2e" metalness={0.9} roughness={0.15} />
        </mesh>

        {/* Underbody */}
        <mesh position={[0, -0.35, 0]}>
          <boxGeometry args={[2.0, 0.1, 4.3]} />
          <meshStandardMaterial color="#0a0a0a" metalness={0.5} roughness={0.8} />
        </mesh>
      </group>

      {/* Wheels */}
      <Wheel
        position={[-1.1, 0, 1.4]}
        rotationSpeed={wheelSpeed}
        steerAngle={steerAngle}
        isFront={true}
      />
      <Wheel
        position={[1.1, 0, 1.4]}
        rotationSpeed={wheelSpeed}
        steerAngle={steerAngle}
        isFront={true}
      />
      <Wheel
        position={[-1.1, 0, -1.4]}
        rotationSpeed={wheelSpeed}
        steerAngle={0}
        isFront={false}
      />
      <Wheel
        position={[1.1, 0, -1.4]}
        rotationSpeed={wheelSpeed}
        steerAngle={0}
        isFront={false}
      />

      {/* Particle Effects */}
      <ParticleEffects
        speed={d.speed}
        accelerator={d.accelerator}
        steering={d.steeringNorm}
        isBraking={d.isBraking}
      />
    </group>
  );
}

export default VehicleModel;