const previewRoot = document.getElementById("preview-root");
const buttons = document.querySelectorAll(".style-button");
const STORAGE_KEY = "platform-style-theme";

function applyTheme(theme) {
  if (!theme) {
    return;
  }

  previewRoot.classList.remove("theme-refine", "theme-workspace", "theme-admin");
  previewRoot.classList.add(theme);

  buttons.forEach((item) => {
    item.classList.toggle("is-active", item.dataset.theme === theme);
  });
}

const savedTheme = window.localStorage.getItem(STORAGE_KEY);
if (savedTheme) {
  applyTheme(savedTheme);
}

buttons.forEach((button) => {
  button.addEventListener("click", () => {
    const theme = button.dataset.theme;
    if (!theme) {
      return;
    }

    applyTheme(theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  });
});
