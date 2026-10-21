document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const messageDiv = document.getElementById("message");
  const searchInput = document.getElementById("search");
  const categoryFilter = document.getElementById("category-filter");
  const sortSelect = document.getElementById("sort");
  const accountBtn = document.getElementById("account-btn");
  const accountMenu = document.getElementById("account-menu");
  const accountStatus = document.getElementById("account-status");
  const loginOpen = document.getElementById("login-open");
  const logoutBtn = document.getElementById("logout-btn");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const registerDialog = document.getElementById("register-dialog");
  const registerForm = document.getElementById("register-form");
  const registerActivityLabel = document.getElementById("register-activity-label");

  const TOKEN_KEY = "mergington-teacher-token";
  let activities = {};
  let teacherUsername = null;
  let registerActivity = "";

  function token() {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  function authHeaders(extra = {}) {
    const headers = { ...extra };
    if (token()) {
      headers.Authorization = "Bearer " + token();
    }
    return headers;
  }

  function showMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    window.setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  function setLoggedIn(username) {
    teacherUsername = username;
    accountStatus.textContent = username
      ? `Logged in as ${username}`
      : "Students can browse activities.";
    loginOpen.classList.toggle("hidden", Boolean(username));
    logoutBtn.classList.toggle("hidden", !username);
    renderActivities();
  }

  function spotsLeft(details) {
    return Math.max(0, details.max_participants - details.participants.length);
  }

  function filteredActivities() {
    const query = searchInput.value.trim().toLowerCase();
    const category = categoryFilter.value;
    const entries = Object.entries(activities).filter(([name, details]) => {
      if (category && details.category !== category) {
        return false;
      }
      if (!query) {
        return true;
      }
      const haystack = [name, details.description, details.schedule, details.category]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });

    entries.sort((left, right) => {
      if (sortSelect.value === "time") {
        const byTime = Number(left[1].start_minutes) - Number(right[1].start_minutes);
        if (byTime !== 0) {
          return byTime;
        }
      }
      return left[0].localeCompare(right[0]);
    });
    return entries;
  }

  function fillCategories() {
    const selected = categoryFilter.value;
    const categories = [...new Set(Object.values(activities).map((item) => item.category))]
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b));
    categoryFilter.replaceChildren(new Option("All categories", ""));
    categories.forEach((category) => {
      categoryFilter.append(new Option(category, category));
    });
    if (categories.includes(selected)) {
      categoryFilter.value = selected;
    }
  }

  function renderActivities() {
    const entries = filteredActivities();
    activitiesList.replaceChildren();

    if (entries.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No activities match those filters.";
      activitiesList.append(empty);
      return;
    }

    entries.forEach(([name, details]) => {
      const card = document.createElement("article");
      card.className = "activity-card";

      const title = document.createElement("h4");
      title.textContent = name;
      card.append(title);

      if (details.category) {
        const badge = document.createElement("span");
        badge.className = "category-badge";
        badge.textContent = details.category;
        card.append(badge);
      }

      if (typeof details.image === "string" && details.image.startsWith("/uploads/")) {
        const image = document.createElement("img");
        image.className = "activity-image";
        image.src = details.image;
        image.alt = `${name} image`;
        card.append(image);
      }

      if (teacherUsername) {
        card.append(buildImageForm(name, Boolean(details.image)));
      }

      const description = document.createElement("p");
      description.textContent = details.description;
      const schedule = document.createElement("p");
      schedule.append(strong("Schedule: "), details.schedule);
      const availability = document.createElement("p");
      availability.append(strong("Availability: "), `${spotsLeft(details)} spots left`);
      card.append(description, schedule, availability);

      if (teacherUsername) {
        const actions = document.createElement("div");
        actions.className = "card-actions";
        const registerBtn = document.createElement("button");
        registerBtn.type = "button";
        registerBtn.textContent = "Register student";
        registerBtn.disabled = spotsLeft(details) === 0;
        registerBtn.addEventListener("click", () => openRegister(name));
        actions.append(registerBtn);
        card.append(actions);
      }

      card.append(buildParticipants(name, details.participants));
      activitiesList.append(card);
    });
  }

  function strong(text) {
    const node = document.createElement("strong");
    node.textContent = text;
    return node;
  }

  function buildImageForm(name, hasImage) {
    const form = document.createElement("form");
    form.className = "image-upload";
    const label = document.createElement("label");
    label.className = "image-upload-label";
    label.textContent = "Activity image";
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/gif,image/webp";
    label.append(input);
    const upload = document.createElement("button");
    upload.type = "submit";
    upload.textContent = "Upload image";
    form.append(label, upload);
    if (hasImage) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-image-btn";
      remove.textContent = "Remove image";
      remove.addEventListener("click", () => handleImageRemove(name));
      form.append(remove);
    }
    form.addEventListener("submit", (event) => handleImageUpload(event, name, input));
    return form;
  }

  function buildParticipants(name, participants) {
    const container = document.createElement("div");
    container.className = "participants-container";
    const section = document.createElement("div");
    section.className = "participants-section";
    const heading = document.createElement("h5");
    heading.textContent = "Participants:";
    section.append(heading);

    if (!participants.length) {
      const empty = document.createElement("p");
      empty.textContent = "No participants yet";
      section.append(empty);
    } else {
      const list = document.createElement("ul");
      participants.forEach((email) => {
        const item = document.createElement("li");
        const emailNode = document.createElement("span");
        emailNode.className = "participant-email";
        emailNode.textContent = email;
        item.append(emailNode);
        if (teacherUsername) {
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "delete-btn";
          remove.textContent = "Remove";
          remove.addEventListener("click", () => handleUnregister(name, email));
          item.append(remove);
        }
        list.append(item);
      });
      section.append(list);
    }

    container.append(section);
    return container;
  }

  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      if (!response.ok) {
        throw new Error("Failed to load activities");
      }
      activities = await response.json();
      fillCategories();
      renderActivities();
    } catch (error) {
      activitiesList.replaceChildren();
      const failure = document.createElement("p");
      failure.textContent = "Failed to load activities. Please try again later.";
      activitiesList.append(failure);
      console.error("Error fetching activities:", error);
    }
  }

  async function refreshSession() {
    if (!token()) {
      setLoggedIn(null);
      return;
    }
    try {
      const response = await fetch("/me", { headers: authHeaders() });
      const result = await response.json();
      if (result.logged_in) {
        setLoggedIn(result.username);
      } else {
        sessionStorage.removeItem(TOKEN_KEY);
        setLoggedIn(null);
      }
    } catch (error) {
      console.error("Error checking session:", error);
      setLoggedIn(null);
    }
  }

  function openRegister(name) {
    registerActivity = name;
    registerActivityLabel.textContent = name;
    registerForm.reset();
    registerDialog.showModal();
  }

  async function handleImageUpload(event, activity, fileInput) {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
      showMessage("Choose an image to upload.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`/activities/${encodeURIComponent(activity)}/image`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to upload image. Please try again.", "error");
      console.error("Error uploading image:", error);
    }
  }

  async function handleImageRemove(activity) {
    try {
      const response = await fetch(`/activities/${encodeURIComponent(activity)}/image`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to remove image. Please try again.", "error");
      console.error("Error removing image:", error);
    }
  }

  async function handleUnregister(activity, email) {
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/unregister?email=${encodeURIComponent(email)}`,
        { method: "DELETE", headers: authHeaders() }
      );
      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  accountBtn.addEventListener("click", () => {
    const open = accountMenu.classList.toggle("hidden") === false;
    accountBtn.setAttribute("aria-expanded", String(open));
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".account")) {
      accountMenu.classList.add("hidden");
      accountBtn.setAttribute("aria-expanded", "false");
    }
  });

  loginOpen.addEventListener("click", () => {
    accountMenu.classList.add("hidden");
    loginForm.reset();
    loginDialog.showModal();
  });
  document.getElementById("login-cancel").addEventListener("click", () => loginDialog.close());
  document.getElementById("register-cancel").addEventListener("click", () => registerDialog.close());

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        showMessage(result.detail || "Login failed", "error");
        return;
      }
      sessionStorage.setItem(TOKEN_KEY, result.token);
      loginDialog.close();
      setLoggedIn(result.username);
      showMessage(`Welcome, ${result.username}.`, "success");
    } catch (error) {
      showMessage("Failed to log in. Please try again.", "error");
      console.error("Error logging in:", error);
    }
  });

  logoutBtn.addEventListener("click", async () => {
    try {
      await fetch("/logout", { method: "POST", headers: authHeaders() });
    } catch (error) {
      console.error("Error logging out:", error);
    }
    sessionStorage.removeItem(TOKEN_KEY);
    accountMenu.classList.add("hidden");
    setLoggedIn(null);
    showMessage("Logged out.", "success");
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = document.getElementById("email").value;
    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(registerActivity)}/signup?email=${encodeURIComponent(email)}`,
        { method: "POST", headers: authHeaders() }
      );
      const result = await response.json();
      if (response.ok) {
        registerDialog.close();
        showMessage(result.message, "success");
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  searchInput.addEventListener("input", renderActivities);
  categoryFilter.addEventListener("change", renderActivities);
  sortSelect.addEventListener("change", renderActivities);

  refreshSession();
  fetchActivities();
});
