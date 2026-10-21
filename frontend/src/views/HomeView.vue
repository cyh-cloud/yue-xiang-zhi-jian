<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { getHomeStats, type HomeStats } from "@/api/public";

type StatKey = keyof HomeStats;
type StatsState = Record<StatKey, number | null>;

const router = useRouter();
const canvas = ref<HTMLCanvasElement | null>(null);
const stats = ref<StatsState>({
  farmers: null,
  courses: null,
  jobs: null,
});

let particleFrame = 0;
let navigationTimer = 0;
let resizeTimer = 0;
let particleResizeHandler: (() => void) | null = null;
let lastFiredAt = 0;
let travel = 0;
let gestureStartedAt = 0;
let wheelArmed = false;
let particles: Array<{
  x: number;
  y: number;
  size: number;
  speedX: number;
  speedY: number;
  opacity: number;
}> = [];
let lastTouchY: number | null = null;

const STAT_LABELS: Readonly<Record<StatKey, string>> = {
  farmers: "服务农户",
  courses: "培训课程",
  jobs: "就业对接",
};

const STAT_KEYS: StatKey[] = ["farmers", "courses", "jobs"];

async function loadStats(): Promise<void> {
  try {
    const response = await getHomeStats();
    stats.value = {
      farmers: response.stats.farmers,
      courses: response.stats.courses,
      jobs: response.stats.jobs,
    };
  } catch {
    stats.value = {
      farmers: null,
      courses: null,
      jobs: null,
    };
  }
}

function statValue(key: StatKey): string {
  const value = stats.value[key];
  return value === null ? "-" : value.toLocaleString("zh-CN");
}

function goToAgriculture(): void {
  const now = Date.now();
  if (now - lastFiredAt < 1200) return;
  lastFiredAt = now;
  document.body.classList.add("scroll-nav-leaving");
  navigationTimer = window.setTimeout(() => {
    document.body.classList.remove("scroll-nav-leaving");
    void router.push("/agriculture");
  }, 420);
}

function handleWheel(event: WheelEvent): void {
  if (event.deltaY < 0) {
    travel = 0;
    wheelArmed = false;
    gestureStartedAt = 0;
    return;
  }

  if (!wheelArmed) {
    wheelArmed = true;
    travel = 0;
    gestureStartedAt = 0;
  }
  trackGesture(event.deltaY);
}

function trackGesture(distance: number): void {
  if (distance < 0) {
    travel = 0;
    gestureStartedAt = 0;
    return;
  }
  if (!gestureStartedAt) gestureStartedAt = Date.now();
  travel += distance;
  document.body.classList.toggle("scroll-nav-hint-gone", travel > 20);
  if (travel < 220) return;

  if (Date.now() - gestureStartedAt > 500) {
    travel = 0;
    gestureStartedAt = 0;
    return;
  }
  goToAgriculture();
}

function handleTouchStart(event: TouchEvent): void {
  lastTouchY = event.touches[0]?.clientY ?? null;
  travel = 0;
  gestureStartedAt = 0;
}

function handleTouchMove(event: TouchEvent): void {
  if (lastTouchY === null) return;
  const currentY = event.touches[0]?.clientY ?? lastTouchY;
  trackGesture(lastTouchY - currentY);
  lastTouchY = currentY;
}

function handleTouchEnd(): void {
  lastTouchY = null;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "PageDown" || event.key === "ArrowDown" || event.key === " ") {
    goToAgriculture();
  }
}

function setupParticles(): void {
  const element = canvas.value;
  const parent = element?.parentElement;
  if (!element || !parent) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const context = element.getContext("2d");
  if (!context) return;

  const resize = (): void => {
    element.width = parent.offsetWidth;
    element.height = parent.offsetHeight;
    particles = createParticles(element.width, element.height);
  };

  const draw = (): void => {
    context.clearRect(0, 0, element.width, element.height);
    for (const particle of particles) {
      particle.x += particle.speedX;
      particle.y += particle.speedY;
      if (particle.x < 0) particle.x = element.width;
      if (particle.x > element.width) particle.x = 0;
      if (particle.y < 0) particle.y = element.height;
      if (particle.y > element.height) particle.y = 0;
      context.beginPath();
      context.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
      context.fillStyle = `rgba(255, 255, 255, ${particle.opacity})`;
      context.fill();
    }
    particleFrame = window.requestAnimationFrame(draw);
  };

  particleResizeHandler = (): void => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(resize, 200);
  };

  resize();
  draw();
  window.addEventListener("resize", particleResizeHandler);
}

function createParticles(width: number, height: number) {
  const count = Math.floor((width * height) / 35000);
  return Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    size: Math.random() * 1.5 + 0.5,
    speedX: (Math.random() - 0.5) * 0.2,
    speedY: (Math.random() - 0.5) * 0.2,
    opacity: Math.random() * 0.3 + 0.1,
  }));
}

onMounted(() => {
  void loadStats();
  setupParticles();
  window.addEventListener("wheel", handleWheel, { passive: true });
  window.addEventListener("touchstart", handleTouchStart, { passive: true });
  window.addEventListener("touchmove", handleTouchMove, { passive: true });
  window.addEventListener("touchend", handleTouchEnd, { passive: true });
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.cancelAnimationFrame(particleFrame);
  window.clearTimeout(navigationTimer);
  window.clearTimeout(resizeTimer);
  if (particleResizeHandler) {
    window.removeEventListener("resize", particleResizeHandler);
  }
  window.removeEventListener("wheel", handleWheel);
  window.removeEventListener("touchstart", handleTouchStart);
  window.removeEventListener("touchmove", handleTouchMove);
  window.removeEventListener("touchend", handleTouchEnd);
  window.removeEventListener("keydown", handleKeydown);
  document.body.classList.remove("scroll-nav-leaving", "scroll-nav-hint-gone");
});
</script>

<template>
  <section
    id="hero"
    class="hero"
    data-testid="home-hero"
  >
    <canvas
      ref="canvas"
      class="hero-particles"
      aria-hidden="true"
    />
    <div
      class="hero-grid-lines"
      aria-hidden="true"
    />
    <div class="hero-content">
      <div class="hero-badge">
        AI + 乡村振兴
      </div>
      <h1 class="hero-title">
        AI驱动的<br>农村人才赋能平台
      </h1>
      <p class="hero-subtitle">
        融合人工智能与本土文化，为广东农村人才提供技能培训、电商运营、非遗传承一站式解决方案
      </p>
      <div class="hero-actions">
        <RouterLink
          class="btn btn-primary btn-lg"
          to="/agriculture"
        >
          开始学习
          <i
            class="fas fa-arrow-right"
            aria-hidden="true"
          />
        </RouterLink>
      </div>
    </div>

    <dl
      class="hero-stats"
      aria-label="平台统计"
    >
      <template
        v-for="(key, index) in STAT_KEYS"
        :key="key"
      >
        <div
          v-if="index > 0"
          class="stat-divider"
          aria-hidden="true"
        />
        <div class="stat-item">
          <dt class="stat-label">
            {{ STAT_LABELS[key] }}
          </dt>
          <dd
            class="stat-number"
            :data-testid="`home-stat-${key}`"
          >
            {{ statValue(key) }}
          </dd>
        </div>
      </template>
    </dl>

    <div
      class="scroll-nav-hint"
      data-testid="home-scroll-hint"
      aria-hidden="true"
    >
      <i class="fas fa-chevron-down" />
      <span>下滑进入农业技能</span>
    </div>
  </section>
</template>

<style src="./home/home.css"></style>
