<script setup>

import { ref, shallowRef } from "vue";
import { getDataOrPopupError, postDataOrPopupError, addPopup } from "@/assets/utils"
import IconCross from '@/components/icons/iconCross.vue'
import IconCheck from '@/components/icons/iconCheck.vue'
import GroupedForm from "@/components/GroupedForm.vue"
import { store, currentSettings } from "@/assets/store";
import { useRouter } from "vue-router"

const router = useRouter()
const props = defineProps({
  session: String,
})

if (props.session) {
  store.session = props.session
}

const userInterfaceOptionGroup = {
  name: "UI Settings",
  options: [
    // {
    //   id: "name",
    //   name: "Name",
    //   type: "text",
    //   placeholder: "xxx",
    //   default_value: undefined
    // },
    {
      id: "theme",
      name: "Theme",
      type: "select",
      default_value: store.theme,
      alternatives: [
        {
          name: "White",
          value: "white"
        },
        {
          name: "Red",
          value: "red"
        },
        {
          name: "Yellow",
          value: "yellow"
        },
        {
          name: "Green",
          value: "green"
        },
        {
          name: "Blue",
          value: "blue"
        },
        {
          name: "Glass",
          value: "glass"
        },
      ]
    },
    {
      id: "fontSize",
      name: "Font Size",
      type: "text",
      placeholder: "Unit is pixel",
      default_value: "16",
    }
  ]
}

const connectionOptionGroup = {
  name: "Connection Settings",
  options: [
    {
      id: "proxy",
      name: "Proxy",
      type: "text",
      placeholder: "http://127.0.0.1:7890",
      default_value: "",
    }
  ]
}

const othersOptionGroup = {
  name: "Other Settings",
  options: [
    {
      id: "filesizeUnit",
      name: "File size unit",
      type: "select",
      default_value: 1024,
      alternatives: [
        {
          name: "KiB, MiB...",
          value: 1024
        },
        {
          name: "KB, MB...",
          value: 1000
        },
      ]
    },
  ]
}

const optionsGroups = shallowRef([userInterfaceOptionGroup, connectionOptionGroup, othersOptionGroup])

async function saveSettings() {
  let settings = { ...currentSettings }
  console.log(settings)
  await postDataOrPopupError("/settings", settings)
  addPopup("green", "Saved successfully", "Settings saved to local database")
}

// actions

const testProxySite = ref("apple")

async function onTestProxy() {
  const data = await getDataOrPopupError("/utils/test_proxy", {
    params: {
      proxy: currentSettings.proxy,
      site: testProxySite.value
    }
  })
  if (data) {
    addPopup("green", "Proxy test success", `Able to connect to ${testProxySite.value} server`)
  } else {
    addPopup("yellow", "Proxy test failed", `Unable to connect to ${testProxySite.value} server`)
  }
}

function onUpdateSettings(optionId, value) {
  currentSettings[optionId] = value
}

let buttons = [
  {
    "label": "Discard",
  },
  {
    "label": "Save",
  }
]

function onButtonClick(button) {
  console.log(button)
  if (button.label == "Discard") {
    router.go(-1)
  } else if (button.label == "Save") {
    saveSettings()
  }
}

</script>

<template>
  <GroupedForm :groups="optionsGroups" :modelValue="currentSettings" @update:modelValue="onUpdateSettings"
    :buttons="buttons" @button-click="onButtonClick">

  </GroupedForm>

  <div class="actions shadow-box">
    <button class="button" @click="onTestProxy">Test Proxy</button>
    <select name="testProxySites" id="testProxySites" v-model="testProxySite">
      <option value="apple">Apple server</option>
      <option value="google">Google server</option>
      <option value="cloudflare">CloudFlare server</option>
      <option value="microsoft">Microsoft server</option>
      <option value="huawei">Huawei server</option>
      <option value="xiaomi">Xiaomi server</option>
    </select>
  </div>
</template>

<style scoped>
.actions {
  width: 60%;
  margin-top: 20px;
  margin-left: 20%;
  margin-right: 20%;
  height: 70px;
  background-color: var(--background-color-2);
  border-radius: 20px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: left;
  padding-left: 5%;
  padding-right: 5%;
}

.actions button,
.actions input {
  height: 50%;
}

.actions select {
  height: 50%;
  min-width: 50px;
  border-radius: 20px;
  border: none;
  outline: 2px solid #ffffff00;
  background-color: var(--background-color-3);
  color: var(--font-color-primary);
  font-size: 1rem;
  padding-left: 10px;
  padding-right: 10px;
  transition: outline-color 0.3s ease;
}
</style>
