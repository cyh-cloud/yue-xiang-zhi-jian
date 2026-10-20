<script setup lang="ts">
import CopywritingTraining from "@/components/ecommerce/CopywritingTraining.vue";
import CustomerServiceTraining from "@/components/ecommerce/CustomerServiceTraining.vue";
import LiveScriptTraining from "@/components/ecommerce/LiveScriptTraining.vue";
</script>

<template>
  <section
    id="ecommerce-tab"
    class="tab-content active"
    data-testid="ecommerce-page"
  >
    <div class="container">
      <div class="section-label">
        E-Commerce
      </div>
      <h1 class="section-title">
        电商运营实训
      </h1>
      <p class="section-desc">
        模拟直播后台，使用 AI 生成带货话术、商品文案与客服对练，完成从初稿到提交的学习闭环
      </p>

      <LiveScriptTraining />
      <CopywritingTraining />
      <CustomerServiceTraining />
    </div>
  </section>
</template>

<style scoped>
#ecommerce-tab {
  min-height: calc(100vh - 72px);
}

#ecommerce-tab .container {
  padding-bottom: 48px;
}
</style>
