<script setup>
import { addPopup, getCurrentApiUrl, getDataOrPopupError } from '@/assets/utils';
import { ref } from 'vue';

const version = ref("Unknown Version")

setTimeout(async () => {
  let serverVersion = await getDataOrPopupError("/utils/version")
  version.value = `v${serverVersion}`
}, 0)

async function checkUpdate() {
  let updateCheckInfo = await getDataOrPopupError("/utils/check_update")
  console.log(updateCheckInfo)
  // Object { has_new_version: false, current_version: "0.1.0", new_version: "0.1.0" }
  if (!updateCheckInfo.has_new_version) {
    addPopup("green", "No updates available", `Current version ${updateCheckInfo.current_version} is the latest`)
  } else {
    addPopup("blue", "New version detected!", `Latest version is ${updateCheckInfo.new_version}, current version ${updateCheckInfo.current_version}`)
  }
}


</script>

<template>
  <div class="info-main">
    <div class="info-panel shadow-box">
      <!-- TODO: 把这个界面做得更美观一点 -->
      <h1>EtherGhost</h1>
      <p>{{ version }}</p>
      <p>
        <a href="https://github.com/Marven11/EtherGhost">Github</a>
        | <a href="https://github.com/Marven11/EtherGhost/issues">Report issues and feature requests</a>
      </p>
      <div class="actions">
        <div class="button" @click="checkUpdate">Check Update</div>

      </div>
    </div>

  </div>
</template>

<style scoped>
.info-main {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.info-panel {
  background-color: var(--background-color-2);
  height: max-content;
  width: 30%;
  border-radius: 20px;
  color: var(--font-color-secondary);
  padding: 2rem;
}

.info-panel h1 {
  color: var(--font-color-primary);

}

.info-value {
  font-weight: bold;
  color: var(--font-color-primary);
}

.actions {
  width: max-content;
}
</style>
