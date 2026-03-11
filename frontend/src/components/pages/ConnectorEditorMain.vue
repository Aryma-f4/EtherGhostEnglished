<script setup>
import { ref, shallowRef, reactive } from "vue";
import { getDataOrPopupError, postDataOrPopupError, addPopup, doAssert } from "@/assets/utils"
import GroupedForm from "@/components/GroupedForm.vue"
import { store } from "@/assets/store";
import { useRouter } from "vue-router"

const router = useRouter()
const props = defineProps({
  connector: String,
})

if (props.connector) {
  store.connector = props.connector
}

const basicOptionGroup = {
  name: "Basic Settings",
  options: [
    {
      id: "name",
      name: "Name",
      type: "text",
      placeholder: "Connector name",
      default_value: undefined
    },
    {
      id: "note",
      name: "Note",
      type: "text",
      placeholder: "Connector note...",
      default_value: "No note"
    },
    {
      id: "connector_type",
      name: "Type",
      type: "select",
      default_value: undefined,
      alternatives: []
    },
    {
      id: "autostart",
      name: "Auto start with main program",
      type: "checkbox",
      default_value: false
    }
  ]
}

const optionValues = reactive({
  name: "",
  connector_type: "",
  note: "No note",
  autostart: false
})
const optionsGroups = shallowRef([])

async function updateOption(connectorType) {
  let options = await getDataOrPopupError(`/connectortype/${connectorType}/conn_options`)
  optionsGroups.value = [basicOptionGroup, ...options]
  for (let group of optionsGroups.value) {
    for (let option of group.options) {
      if (option.default_value !== undefined && option.default_value !== null) {
        optionValues[option.id] = option.default_value
      }
    }
  }
}

async function fetchSupportedConnectorTypes() {
  const data = await getDataOrPopupError("/connectortype")
  let optionIdx = basicOptionGroup.options.findIndex(option => option.id == 'connector_type')
  basicOptionGroup.options[optionIdx].alternatives = data.map(connectorType => {
    return {
      name: connectorType.name,
      value: connectorType.type
    }
  })
}

async function fetchCurrentConnector() {
  const connector = await getDataOrPopupError(`/connector/${props.connector}`)
  await updateOption(connector.connector_type)
  for (const group of optionsGroups.value) {
    for (const option of group.options) {
      doAssert(["text", "checkbox", "select"].includes(option.type), "Internal Error: unknown option type")
      if (["name", "connector_type", "note", "autostart"].includes(option.id)) {
        optionValues[option.id] = connector[option.id]
      } else if (connector.connection[option.id] !== undefined && connector.connection[option.id] !== null) {
        optionValues[option.id] = connector.connection[option.id]
      }
    }
  }
}

function getCurrentConnector() {
  let connector = { connection: {} }
  if (!optionValues["connector_type"]) {
    return undefined;
  }
  for (const group of optionsGroups.value) {
    for (const option of group.options) {
      doAssert(["text", "checkbox", "select"].includes(option.type), "Internal Error: unknown option type")
      if (optionValues[option.id] === undefined || optionValues[option.id] == null) {
        if (option.type !== "checkbox") {
          addPopup("red", `Option ${option.name} not filled`, `Option ${option.name} is not filled; cannot get current configuration!`)
          return undefined
        }
      }
      if (["name", "connector_type", "note", "autostart"].includes(option.id)) {
        connector[option.id] = optionValues[option.id]
      } else {
        connector.connection[option.id] = optionValues[option.id]
      }
    }
  }
  if (store.connector) {
    connector.connector_id = store.connector;
  } else {
    // Generate a new UUID
    connector.connector_id = crypto.randomUUID();
  }
  return connector
}

async function saveConnector() {
  let connector = getCurrentConnector()
  if (!connector) return;
  let result = await postDataOrPopupError("/connector", connector)
  if (!result) {
    addPopup("red", "Save failed", "Failed to save connector to local database")
  } else {
    addPopup("green", "Saved successfully", `${result.action === 'add' ? 'Added' : 'Updated'} connector to local database successfully`)
    setTimeout(() => {
      router.push("/connector")
    }, 1000);
  }
}

function onUpdateOption(optionId, value) {
  optionValues[optionId] = value
  // If connector_type changes, reload options
  if (optionId === "connector_type") {
    updateOption(value)
  }
}

const buttons = [
  { label: "Cancel" },
  { label: "Save" },
]

function onButtonClick(button) {
  if (button.label === "Cancel") {
    router.push("/connector")
  } else if (button.label === "Save") {
    saveConnector()
  }
}

setTimeout(async () => {
  await fetchSupportedConnectorTypes();
  if (props.connector) {
    await fetchCurrentConnector()
  } else {
    // Set default connector type
    if (basicOptionGroup.options.find(opt => opt.id === 'connector_type').alternatives.length > 0) {
      const defaultType = basicOptionGroup.options.find(opt => opt.id === 'connector_type').alternatives[0].value
      optionValues.connector_type = defaultType
      await updateOption(defaultType)
    }
  }
}, 0)
</script>

<template>
  <GroupedForm :groups="optionsGroups" :modelValue="optionValues" @update:modelValue="onUpdateOption" :buttons="buttons"
    @button-click="onButtonClick" />
</template>
