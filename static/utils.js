function showToast(message, duration = 2000) {
    // 1. Create the toast element
    const toast = document.createElement("div");
    toast.textContent = message;
  
    // 2. Add basic styling
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "20px",
      left: "50%",
      transform: "translateX(-50%)",
      backgroundColor: "#333",
      color: "#fff",
      padding: "10px 20px",
      borderRadius: "5px",
      zIndex: "1000",
      fontSize: "14px",
      opacity: "0",
      transition: "opacity 0.5s ease"
    });
  
    // 3. Add to the DOM and trigger fade-in
    document.body.appendChild(toast);
    setTimeout(() => toast.style.opacity = "1", 10);
  
    // 4. Remove after the specified duration
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 500); // Wait for fade-out to finish
    }, duration);
  }


function normalize_map_value(value) {
  if (typeof value !== "string") return "";
  return value.trim();
}

