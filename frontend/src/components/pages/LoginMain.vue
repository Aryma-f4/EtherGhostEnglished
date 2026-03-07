<script setup>
import { ref } from "vue";
import { postDataOrPopupError } from "@/assets/utils";
import { useRouter } from "vue-router";

const router = useRouter()
const username = ref("")
const password = ref("")
const loading = ref(false)

async function onSubmit(e) {
  e.preventDefault()
  loading.value = true
  try {
    const ok = await postDataOrPopupError("/auth/login", {
      username: username.value,
      password: password.value,
    })
    if (ok) {
      router.push("/")
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-main">
    <form class="login-panel shadow-box" @submit="onSubmit">
      <h2>Login</h2>
      <input type="text" placeholder="Username" v-model="username" required>
      <input type="password" placeholder="Password" v-model="password" required>
      <button :disabled="loading">{{ loading ? "Signing in..." : "Sign in" }}</button>
    </form>
  </div>
</template>

<style scoped>
.login-main {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-panel {
  width: 400px;
  padding: 20px;
  border-radius: 20px;
  background-color: var(--background-color-2);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.login-panel input, .login-panel button {
  height: 40px;
  border: none;
  border-radius: 12px;
  outline: none;
  padding: 0 12px;
  color: var(--font-color-primary);
  background-color: var(--background-color-3);
}
.login-panel button {
  background-color: var(--primary-color);
  color: var(--font-color-black);
}
</style>
