import { apiFetch, getSession } from "/src/shared.js?v=20261101-3";

const form = document.getElementById("login-form");
const errorEl = document.getElementById("login-error");
const button = document.getElementById("login-btn");

getSession().then((s) => { if (s.authenticated) location.replace("/dashboard/fan/"); });

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  button.disabled = true;
  try {
    await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("username").value.trim(),
        password: document.getElementById("password").value,
      }),
    });
    location.href = "/dashboard/fan/";
  } catch (err) {
    errorEl.textContent = err.message;
    document.getElementById("password").value = "";
    button.disabled = false;
  }
});
