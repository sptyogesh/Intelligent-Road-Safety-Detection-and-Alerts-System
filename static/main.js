const menuToggle = document.querySelector('.menu-toggle');
const navMenu = document.querySelector('nav ul');

menuToggle.addEventListener('click', () => {
    navMenu.classList.toggle('show');
});
//colapsible
document.querySelectorAll('.collapsible').forEach(item => {
    item.addEventListener('click', () => {
        const content = item.nextElementSibling; // Get the next sibling (the paragraph)
        if (content.style.display === "block") {
            content.style.display = "none";
        } else {
            content.style.display = "block";
        }
    });
});

const registerButton = document.getElementById('registerBtn');
const loginButton = document.getElementById('loginBtn');
const registerModal = document.getElementById('registerModal');
const loginModal = document.getElementById('loginModal');
const closeRegister = document.getElementById('closeRegister');
const closeLogin = document.getElementById('closeLogin');

// Open Login Modal (for Register Complaint)
registerButton.addEventListener('click', (event) => {
    event.preventDefault();
    loginModal.style.display = 'block'; // Open login modal
    registerModal.style.display = 'none'; // Ensure register modal is closed
    disableButtons(true); // Disable other buttons
});

// Open Register Modal (for Login)
loginButton.addEventListener('click', (event) => {
    event.preventDefault();
    registerModal.style.display = 'block'; // Open register modal
    loginModal.style.display = 'none'; // Ensure login modal is closed
    disableButtons(true); // Disable other buttons
});

// Close Register Modal
closeRegister.onclick = function() {
    closeModal(registerModal);
};

// Close Login Modal
closeLogin.onclick = function() {
    closeModal(loginModal);
};

// Function to close modal with animation
function closeModal(modal) {
    const modalContent = modal.querySelector('.modal-content');
    modal.classList.add('fade-out');
    modalContent.classList.add('fade-out');

    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('fade-out');
        modalContent.classList.remove('fade-out');
        disableButtons(false); // Enable buttons
    }, 300); // Match the timeout with the animation duration
}

// Function to disable/enable buttons
function disableButtons(disable) {
    const buttons = document.querySelectorAll('nav button');
    buttons.forEach(button => {
        button.disabled = disable;
        button.style.opacity = disable ? '0.5' : '1';
    });
}

// Close modal when clicking outside of the modal content
window.onclick = function(event) {
    if (event.target === registerModal) {
        closeModal(registerModal);
    }
    if (event.target === loginModal) {
        closeModal(loginModal);
    }
};

// Function to handle login form submission
function saveAndNext(event) {
    event.preventDefault();

    const username = document.getElementById('username').value;
    const phone = document.getElementById('phone').value;
    const host = r;

    localStorage.setItem('username', username);
    localStorage.setItem('phone', phone);

    window.location.href = '../personal_details/Index.html'; // Change this to your actual redirect
}

// Form validation function (if needed)
function validateForm() {
    // Add your form validation logic here
    return true; // Return true if valid, false if invalid
}


const imageScrollContainer = document.getElementById('imageScrollContainer');
const scrollingImages = document.getElementById('scrollingImages');

let isMouseDown = false;
let startX;
let scrollLeft;

imageScrollContainer.addEventListener('mousedown', (e) => {
    isMouseDown = true;
    startX = e.pageX - imageScrollContainer.offsetLeft;
    scrollLeft = scrollingImages.scrollLeft;
});

imageScrollContainer.addEventListener('mouseleave', () => {
    isMouseDown = false;
});

imageScrollContainer.addEventListener('mouseup', () => {
    isMouseDown = false;
});

imageScrollContainer.addEventListener('mousemove', (e) => {
    if (!isMouseDown) return; // Stop the function if mouse is not down
    e.preventDefault();
    const x = e.pageX - imageScrollContainer.offsetLeft;
    const walk = (x - startX) * 2; // The multiplier controls the scroll speed
    scrollingImages.scrollLeft = scrollLeft - walk;
});
