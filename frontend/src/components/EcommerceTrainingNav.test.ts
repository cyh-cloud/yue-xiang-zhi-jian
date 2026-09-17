import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import EcommerceTrainingNav from './EcommerceTrainingNav.vue'

const paths = [
  '/student/ecommerce-training',
  '/student/ecommerce-training/live-script',
  '/student/ecommerce-training/simulation',
  '/student/ecommerce-training/copy-training',
  '/student/ecommerce-training/store-guidance',
  '/student/ecommerce-training/customer-service',
  '/student/ecommerce-training/courses'
]

function testRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: paths.map(path => ({
      path,
      component: { template: '<div />' }
    }))
  })
}

describe('EcommerceTrainingNav', () => {
  afterEach(() => {
    delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView
  })

  it('scrolls the route-active item into view on mount and route changes', async () => {
    const scrolledElements: HTMLElement[] = []
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value(this: HTMLElement) {
        scrolledElements.push(this)
      }
    })

    const router = testRouter()
    await router.push('/student/ecommerce-training/copy-training')
    await router.isReady()

    mount(EcommerceTrainingNav, {
      global: {
        plugins: [router]
      }
    })
    await flushPromises()

    expect(
      scrolledElements[scrolledElements.length - 1]?.getAttribute('href')
    ).toBe(
      '/student/ecommerce-training/copy-training'
    )

    await router.push('/student/ecommerce-training/courses')
    await flushPromises()

    expect(
      scrolledElements[scrolledElements.length - 1]?.getAttribute('href')
    ).toBe(
      '/student/ecommerce-training/courses'
    )
  })
})
