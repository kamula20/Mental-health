const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

const showRegister = document.getElementById("showRegister");
const showLogin = document.getElementById("showLogin");

function displayLogin() {
    loginForm.hidden = false;
    registerForm.hidden = true;

    loginTab.classList.add("active");
    registerTab.classList.remove("active");

    clearMessages();
}

function displayRegister() {
    loginForm.hidden = true;
    registerForm.hidden = false;

    registerTab.classList.add("active");
    loginTab.classList.remove("active");

    clearMessages();
}

function clearMessages() {
    document.getElementById("loginMessage").textContent = "";
    document.getElementById("registerMessage").textContent = "";

    document.getElementById("loginMessage").className = "auth-message";
    document.getElementById("registerMessage").className = "auth-message";
}

loginTab.addEventListener("click", displayLogin);
registerTab.addEventListener("click", displayRegister);
showRegister.addEventListener("click", displayRegister);
showLogin.addEventListener("click", displayLogin);

// SHOW AND HIDE PASSWORD

document.querySelectorAll(".toggle-password").forEach(button => {

    button.addEventListener("click", function () {

        const passwordInput = document.getElementById(
            this.dataset.target
        );

        if (passwordInput.type === "password") {
            passwordInput.type = "text";
            this.textContent = "Hide";
        } else {
            passwordInput.type = "password";
            this.textContent = "Show";
        }
    });

});

// REGISTRATION FORM

registerForm.addEventListener("submit", function(event) {

    event.preventDefault();

    const fullName = document.getElementById("fullName").value.trim();
    const email = document.getElementById("registerEmail").value.trim();
    const password = document.getElementById("registerPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    const message = document.getElementById("registerMessage");

    if (fullName.length < 2) {
        message.textContent = "Please enter your full name.";
        message.className = "auth-message error";
        return;
    }

    if (password.length < 8) {
        message.textContent = "Password must contain at least 8 characters.";
        message.className = "auth-message error";
        return;
    }

    if (password !== confirmPassword) {
        message.textContent = "Passwords do not match.";
        message.className = "auth-message error";
        return;
    }

    message.textContent =
        "Registration form validated successfully! Connect a backend to create your account.";

    message.className = "auth-message success";

});

// LOGIN FORM

loginForm.addEventListener("submit", function(event) {

    event.preventDefault();

    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    const message = document.getElementById("loginMessage");

    if (!email || !password) {
        message.textContent = "Please enter your email and password.";
        message.className = "auth-message error";
        return;
    }

    message.textContent =
        "Login form validated! Connect a backend to verify your account.";

    message.className = "auth-message success";

});