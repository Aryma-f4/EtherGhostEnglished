import { reactive, ref, watch } from 'vue'
import { getDataOrPopupError, getDataOrSilentError } from './utils'

// popupsRef is a ref pointing to the Popups component
// Popups is global; there's only one in App.vue
// To add a popup, other modules access this ref and call its functions

export const popupsRef = ref(null)

export const store = reactive({
  session: "",
  sessionName: "",
  theme: "green",
  theme_background_transition: false,
})

export const currentSettings = reactive({
  theme: "green",
  filesizeUnit: 1024
})

document.body.dataset["theme"] = "green"

watch(
  () => store.session,
  async newSession => {
    if (!newSession) {
      store.sessionName = ""
      return;
    }
    let sessionInfo = await getDataOrSilentError(`/session/${newSession}/`)
    store.sessionName = sessionInfo?.name || ""
  }
)

watch(
  () => currentSettings.theme,
  (newValue, oldValue) => {
    store.theme = newValue
    document.querySelector("body").dataset["theme"] = store.theme
  }
)
