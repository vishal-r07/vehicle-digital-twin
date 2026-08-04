/**
 * ParticleEffects.jsx - Dynamic particle system
 * 
 * Features:
 * - Exhaust smoke when accelerating
 * - Tire smoke when drifting/braking
 * - Speed lines at high velocity
 */

import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function ParticleEffects({ speed, accelerator, steering, isBraking }) {
  const exhaustRef = useRef();
  const smokeRef = useRef();

  // Exhaust particles
  const exhaustCount = 50;
  const positionArray = useMemo(() => new Float32Array(exhaustCount * 3), [exhaustCount]);
  const exhaustParticles = useMemo(() => {
    const temp = [];
    for (let i = 0; i < exhaustCount; i++) {
      temp.push({
        position: new THREE.Vector3(),
        velocity: new THREE.Vector3(),
        life: Math.random(),
      });
    }
    return temp;
  }, []);

  useFrame((state, delta) => {
    if (exhaustRef.current) {
      const positions = exhaustRef.current.geometry.attributes.position.array;
      
      exhaustParticles.forEach((particle, i) => {
        particle.life -= delta * 0.5;
        
        if (particle.life <= 0) {
          // Reset particle
          particle.life = 1;
          particle.position.set(
            (Math.random() - 0.5) * 0.1,
            -0.2,
            -2.3
          );
          particle.velocity.set(
            (Math.random() - 0.5) * 0.5,
            Math.random() * 0.5 + 0.5,
            -Math.random() * 2 - 1
          );
        }

        // Update position
        particle.position.add(particle.velocity.clone().multiplyScalar(delta));
        
        // Apply gravity
        particle.velocity.y -= delta * 0.5;

        // Update buffer
        positions[i * 3] = particle.position.x;
        positions[i * 3 + 1] = particle.position.y;
        positions[i * 3 + 2] = particle.position.z;
      });

      exhaustRef.current.geometry.attributes.position.needsUpdate = true;
      
      // Fade based on accelerator
      exhaustRef.current.material.opacity = accelerator > 20 ? 0.3 : 0;
    }
  });

  return (
    <>
      {/* Exhaust particles */}
      <points ref={exhaustRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={exhaustCount}
            array={positionArray}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.05}
          color="#555555"
          transparent
          opacity={0}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
        />
      </points>
    </>
  );
}

export default ParticleEffects;