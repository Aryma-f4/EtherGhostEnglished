<script setup>
import { store } from '@/assets/store';
import { getCurrentApiUrl } from '@/assets/utils';


const props = defineProps({
  session: String,
})

if (props.session) {
  store.session = props.session
}

</script>

<template>
  <div class="info-main">
    <div class="info-panel shadow-box">
      <h1>Integrate AntSword</h1>
      <p>Use the following info to let AntSword connect to the webshell via EtherGhost</p>
      <table>
        <tr>
          <td>URL</td>
          <td class="info-value">{{ getCurrentApiUrl() }}/session/{{ props.session }}/emulated_antsword</td>
        </tr>
        <tr>
          <td>Password</td>
          <td class="info-value">as</td>
        </tr>
      </table>
      <p>Allows AntSword plugins to integrate with EtherGhost, running on Behinder webshells, benefiting from EtherGhost features</p>
      <p>Currently supports PHP webshells only</p>
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
  width: 50%;
  border-radius: 20px;
  color: var(--font-color-secondary);
  padding: 20px;
}

.info-panel h1 {
  color: var(--font-color-primary);

}

.info-panel table {
  width: 100%;
  font-size: 20px;
  color: var(--font-color-secondary);
}

.info-panel td {
  min-width: 100px;
}

.info-value {
  font-weight: bold;
  color: var(--font-color-primary);
}
</style>
