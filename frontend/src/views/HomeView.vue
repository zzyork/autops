<script setup lang="ts">
import ServiceStatus from '@/components/ServiceStatus.vue'
</script>

<template>
  <div class="workspace">
    <header class="topbar">
      <RouterLink to="/" class="brand" aria-label="autops 首页"><span class="brand-mark">a.</span>autops</RouterLink>
      <span class="workspace-label">工作台 <span class="version">v0.1</span></span>
    </header>
    <main>
      <div class="intro">
        <span class="eyebrow">从这里开始</span>
        <h1>让工作，有序发生。</h1>
        <p>欢迎来到 autops。工作台已准备好，下一步从你的业务开始。</p>
      </div>
      <div class="overview">
        <ServiceStatus />
        <section class="welcome-panel" aria-labelledby="welcome-title">
          <span class="eyebrow">新的起点</span>
          <h2 id="welcome-title">留出空间，<br />给接下来的可能。</h2>
          <p>这里将承载你的业务模块、日常操作与关键信息。</p>
          <div class="line-art" aria-hidden="true"><span></span><span></span><span></span></div>
        </section>
      </div>
    </main>
    <footer class="page-footer"><span>autops / 工作台</span><span>准备就绪，持续向前。</span></footer>
  </div>
</template>
