import type { Directive } from 'vue'
import { useAuthStore } from '@/stores/auth'

/** v-permission="'host:create'"：无权限移除元素。超管直通。 */
const directive: Directive<HTMLElement, string | string[]> = {
  mounted(el, binding) {
    const auth = useAuthStore()
    if (auth.user?.is_superuser) return
    const need = Array.isArray(binding.value) ? binding.value : [binding.value]
    const has = need.every((p) => auth.permissions.includes(p))
    if (!has) el.parentNode?.removeChild(el)
  },
}

export default directive
