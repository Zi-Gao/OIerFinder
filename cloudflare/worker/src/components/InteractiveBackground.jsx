import React, { useEffect, useRef } from 'react';

/**
 * A high-performance interactive dot matrix wave background.
 * Refined for silkier flow, eased mouse tracking, and professional subtlety.
 */
const InteractiveBackground = () => {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const smoothedMouse = useRef({ x: -1000, y: -1000 });
  const requestRef = useRef();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width, height;
    let particles = [];
    const spacing = 22; // Denser spacing for a more "finished" look
    const mouseRadius = 200; // Larger influence area for smoothness
    const mouseStrength = 110; // Strong but gradual lift

    const resize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      
      particles = [];
      const margin = 250; // Buffer to prevent empty edges during warping
      for (let x = -margin; x < width + margin; x += spacing) {
        for (let y = -margin; y < height + margin; y += spacing) {
          particles.push({ baseX: x, baseY: y });
        }
      }
    };

    const handleMouseMove = (e) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
      // Handle the initial entry jump from -1000
      if (smoothedMouse.current.x < -500) {
        smoothedMouse.current = { x: e.clientX, y: e.clientY };
      }
    };

    const handleTouchMove = (e) => {
      if (e.touches.length > 0) {
        mouseRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        if (smoothedMouse.current.x < -500) {
          smoothedMouse.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }
      }
    };

    const animate = (time) => {
      const t = time * 0.0008; // Slower, silkier flow
      ctx.clearRect(0, 0, width, height);
      
      // Eased mouse tracking (LERP) for liquid responsiveness
      smoothedMouse.current.x += (mouseRef.current.x - smoothedMouse.current.x) * 0.08;
      smoothedMouse.current.y += (mouseRef.current.y - smoothedMouse.current.y) * 0.08;

      const isDark = document.documentElement.classList.contains('dark');
      const baseColor = isDark ? [255, 255, 255] : [0, 0, 0];

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        
        // --- Liquid Wave Math (Lower frequency, smoother transitions) ---
        // Layer 1: Long rolling swells
        const z1 = Math.sin(p.baseX * 0.002 + t) * Math.cos(p.baseY * 0.002 + t * 0.6) * 70;
        // Layer 2: Subtle horizontal drift
        const z2 = Math.sin(p.baseX * 0.008 - t * 1.2) * 25;
        // Layer 3: Dynamic swaying
        const z3 = Math.sin((p.baseX + p.baseY) * 0.004 + t * 0.4) * 15;
        
        const z = z1 + z2 + z3;

        // --- Smooth Mouse Attraction ---
        const dx = smoothedMouse.current.x - p.baseX;
        const dy = smoothedMouse.current.y - p.baseY;
        const distSq = dx * dx + dy * dy;
        const dist = Math.sqrt(distSq);

        let mouseZ = 0;
        if (dist < mouseRadius) {
          // Cubic easing for silkier attraction (smooth peak)
          const ratio = 1 - dist / mouseRadius;
          mouseZ = (ratio * ratio * ratio) * mouseStrength;
        }

        const totalZ = z + mouseZ;

        // --- Perspective Projection ---
        const perspective = 1100; // Softer perspective projection
        const scale = perspective / (perspective - totalZ);
        
        // Warp coordinates based on depth
        const renderX = p.baseX + (p.baseX - smoothedMouse.current.x) * (scale - 1);
        const renderY = p.baseY + (p.baseY - smoothedMouse.current.y) * (scale - 1);

        // --- Subtle Visuals & Lighting ---
        // Lower opacity range for a professional, "ghostly" silk look
        const opacity = Math.max(0.02, Math.min(0.25, 0.12 + (totalZ / 400)));
        ctx.globalAlpha = opacity;
        ctx.fillStyle = `rgb(${baseColor[0]}, ${baseColor[1]}, ${baseColor[2]})`;

        ctx.beginPath();
        const dotSize = 1.0 * scale; 
        ctx.arc(renderX, renderY, dotSize, 0, Math.PI * 2);
        ctx.fill();
      }
      
      ctx.globalAlpha = 1.0;
      requestRef.current = requestAnimationFrame(animate);
    };

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('touchmove', handleTouchMove);
    
    resize();
    requestRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('touchmove', handleTouchMove);
      cancelAnimationFrame(requestRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
    />
  );
};

export default InteractiveBackground;
