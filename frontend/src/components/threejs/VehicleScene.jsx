/**
 * VehicleScene.jsx - Cinematic Three.js scene with premium environment
 * 
 * Features:
 * - Dynamic camera system with multiple angles
 * - HDR environment lighting
 * - Atmospheric effects
 * - Reflective ground plane
 */

import React, { Suspense, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, ContactShadows, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import VehicleModel from './VehicleModel';
import CameraController from './CameraController';
import GroundEnvironment from './GroundEnvironment';

function VehicleScene({ data }) {
  const isInteractingRef = useRef(false);

  return (
    <div style={{ 
      width: '100%', 
      height: '100%', 
      minHeight: '600px',
      position: 'relative',
      overflow: 'hidden',
      borderRadius: '16px',
      background: 'linear-gradient(180deg, #0a0e17 0%, #1a1f2e 50%, #0f1419 100%)'
    }}>
      <Canvas
        shadows
        gl={{ 
          antialias: true, 
          alpha: false,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.2,
        }}
        dpr={[1, 2]}
      >
        {/* Cinematic Camera */}
        <PerspectiveCamera makeDefault position={[6, 3, 6]} fov={45} />
        <CameraController data={data} isInteractingRef={isInteractingRef} />

        {/* HDR Environment Lighting */}
        <Environment 
          files="https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/industrial_sunset_puresky_1k.hdr"
          background={false}
          intensity={0.8}
        />

        {/* Key Light */}
        <directionalLight
          position={[10, 15, 10]}
          intensity={1.5}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-far={50}
          shadow-camera-left={-10}
          shadow-camera-right={10}
          shadow-camera-top={10}
          shadow-camera-bottom={-10}
          color="#fff5e6"
        />

        {/* Fill Light */}
        <directionalLight
          position={[-8, 8, -5]}
          intensity={0.6}
          color="#4a90e2"
        />

        {/* Rim Light */}
        <pointLight
          position={[-5, 3, 8]}
          intensity={0.8}
          color="#ff6b35"
          distance={15}
        />

        {/* Ambient */}
        <ambientLight intensity={0.15} />

        {/* Fog for atmosphere */}
        <fog attach="fog" args={['#0a0e17', 15, 35]} />

        {/* Vehicle */}
        <Suspense fallback={null}>
          <VehicleModel data={data} />
        </Suspense>

        {/* Ground & Environment */}
        <GroundEnvironment />

        {/* Orbit Controls */}
        <OrbitControls
          enablePan={false}
          enableZoom={true}
          minDistance={4}
          maxDistance={20}
          minPolarAngle={Math.PI / 6}
          maxPolarAngle={Math.PI / 2.2}
          enableDamping={true}
          dampingFactor={0.05}
          rotateSpeed={0.5}
          zoomSpeed={0.8}
          onStart={() => { isInteractingRef.current = true; }}
          onEnd={() => { isInteractingRef.current = false; }}
        />
      </Canvas>

      {/* Overlay UI */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        right: '20px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{
          background: 'rgba(10, 14, 23, 0.8)',
          backdropFilter: 'blur(10px)',
          padding: '12px 20px',
          borderRadius: '12px',
          border: '1px solid rgba(100, 116, 139, 0.3)',
          color: '#94a3b8',
          fontSize: '12px',
          fontFamily: 'var(--font-mono)',
        }}>
          🎥 CINEMATIC VIEW • SCROLL TO ZOOM • DRAG TO ROTATE
        </div>
      </div>
    </div>
  );
}

export default VehicleScene;