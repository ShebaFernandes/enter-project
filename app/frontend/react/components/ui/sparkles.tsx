import Particles, { ParticlesProvider } from "@tsparticles/react";
import type { Container, Engine, ISourceOptions } from "@tsparticles/engine";
import { loadSlim } from "@tsparticles/slim";
import { motion, useAnimation } from "framer-motion";
import { useEffect, useId, useMemo, useState } from "react";

type SparklesProps = {
  id?: string;
  className?: string;
  background?: string;
  particleSize?: number;
  minSize?: number;
  maxSize?: number;
  speed?: number;
  particleColor?: string;
  particleDensity?: number;
};

const initializeSparkles = async (engine: Engine) => {
  await loadSlim(engine);
};

function ParticleField({
  id,
  className = "",
  background = "transparent",
  particleSize,
  minSize = particleSize ?? 0.5,
  maxSize = particleSize ?? 1.35,
  speed = 0.45,
  particleColor = "#ffffff",
  particleDensity = 90,
}: SparklesProps) {
  const generatedId = useId().replaceAll(":", "");
  const controls = useAnimation();
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  const options = useMemo<ISourceOptions>(
    () => ({
      background: { color: { value: background } },
      fullScreen: { enable: false, zIndex: 0 },
      fpsLimit: 60,
      interactivity: {
        events: {
          onClick: { enable: false, mode: [] },
          onHover: { enable: false, mode: [] },
          resize: { enable: true },
        },
      },
      particles: {
        color: { value: particleColor },
        move: {
          direction: "none",
          enable: !reducedMotion,
          outModes: { default: "out" },
          random: true,
          speed: { min: speed * 0.2, max: speed },
          straight: false,
        },
        number: {
          density: { enable: true, width: 500, height: 300 },
          value: particleDensity,
        },
        opacity: {
          value: { min: 0.12, max: 0.7 },
          animation: {
            enable: !reducedMotion,
            speed: Math.max(speed, 0.2),
            sync: false,
          },
        },
        shape: { type: "circle" },
        size: { value: { min: minSize, max: maxSize } },
      },
      detectRetina: true,
      pauseOnBlur: true,
      pauseOnOutsideViewport: true,
    }),
    [
      background,
      maxSize,
      minSize,
      particleColor,
      particleDensity,
      reducedMotion,
      speed,
    ],
  );

  const particlesLoaded = async (container?: Container) => {
    if (!container) return;
    await controls.start({
      opacity: 1,
      transition: { duration: reducedMotion ? 0 : 0.7 },
    });
  };

  if (reducedMotion) {
    return (
      <div
        className={`sparkles-core ${className}`.trim()}
        data-reduced-motion="true"
      />
    );
  }

  return (
    <motion.div
      className={`sparkles-core ${className}`.trim()}
      initial={{ opacity: 0 }}
      animate={controls}
    >
      <Particles
        id={id ?? `sparkles-${generatedId}`}
        className="sparkles-core__canvas"
        particlesLoaded={particlesLoaded}
        options={options}
      />
    </motion.div>
  );
}

export function SparklesCore(props: SparklesProps) {
  return (
    <ParticlesProvider init={initializeSparkles}>
      <ParticleField {...props} />
    </ParticlesProvider>
  );
}
