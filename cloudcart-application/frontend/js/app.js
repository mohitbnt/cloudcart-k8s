import { api } from './api.js';
import { state, productById } from './store.js';
import {
  $, toast, renderFilters, renderProducts, updateAccount, updateCartBadge,
  renderCart, renderCheckout, renderOrders, setAuthMode
} from './ui.js';

function openOverlay(id) {
  const element = $(id);
  element.classList.add('open');
  element.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
}

function closeOverlay(id) {
  const element = $(id);
  element.classList.remove('open');
  element.setAttribute('aria-hidden', 'true');
  if (!document.querySelector('.overlay.open')) document.body.classList.remove('modal-open');
}

async function loadProducts() {
  state.products = await api('/catalog/products');
  renderFilters(setCategory);
  renderProducts(addToCart);
}

function setCategory(category) {
  state.category = category;
  renderFilters(setCategory);
  renderProducts(addToCart);
}

async function refreshCart() {
  if (!state.user) {
    state.cart = { items: [] };
  } else {
    try {
      state.cart = await api('/cart');
    } catch (_) {
      state.cart = { items: [] };
    }
  }
  updateCartBadge();
}

async function refreshOrders() {
  if (!state.user) {
    renderOrders([]);
    return;
  }

  try {
    const orders = await api('/order/orders');
    const mine = orders
      .filter((order) => order.customer_email === state.user.email)
      .reverse();
    renderOrders(mine);
  } catch (error) {
    console.error(error);
  }
}

async function refreshSession() {
  try {
    state.user = await api('/identity/me');
    updateAccount(openLogin, logout);
    await refreshCart();
    await refreshOrders();
  } catch (_) {
    state.user = null;
    updateAccount(openLogin, logout);
    await refreshCart();
    renderOrders([]);
  }
}

function openLogin() {
  setAuthMode('login');
  openOverlay('#authOverlay');
  setTimeout(() => $('#loginEmail').focus(), 50);
}

function openRegister() {
  setAuthMode('register');
  openOverlay('#authOverlay');
  setTimeout(() => $('#registerEmail').focus(), 50);
}

function closeAuth() {
  closeOverlay('#authOverlay');
}

async function login(event) {
  event.preventDefault();
  const button = $('#loginSubmit');
  const error = $('#loginError');
  error.textContent = '';
  button.disabled = true;
  button.textContent = 'Signing in…';

  try {
    state.user = await api('/identity/login', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#loginEmail').value,
        password: $('#loginPassword').value,
      }),
    });

    closeAuth();
    updateAccount(openLogin, logout);
    await refreshCart();
    await refreshOrders();
    toast(`Welcome back, ${state.user.email}`);
  } catch (error) {
    error.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Sign in';
  }
}

async function register(event) {
  event.preventDefault();
  const button = $('#registerSubmit');
  const error = $('#registerError');
  const email = $('#registerEmail').value.trim();
  const password = $('#registerPassword').value;
  const confirmation = $('#registerPasswordConfirm').value;

  error.textContent = '';

  if (password !== confirmation) {
    error.textContent = 'Passwords do not match';
    return;
  }

  if (password.length < 6) {
    error.textContent = 'Password must be at least 6 characters';
    return;
  }

  button.disabled = true;
  button.textContent = 'Creating account…';

  try {
    state.user = await api('/identity/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    closeAuth();
    updateAccount(openLogin, logout);
    await refreshCart();
    await refreshOrders();
    toast(`Welcome to CloudCart, ${state.user.email}`);
    $('#registerForm').reset();
  } catch (error) {
    error.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Create account';
  }
}

async function logout() {
  try {
    await api('/identity/logout', { method: 'POST' });
    state.user = null;
    state.cart = { items: [] };
    updateAccount(openLogin, logout);
    updateCartBadge();
    renderOrders([]);
    toast('You have been signed out');
  } catch (error) {
    toast(error.message);
  }
}

async function requireLogin() {
  if (state.user) return true;
  openLogin();
  toast('Please sign in to use your cart');
  return false;
}

async function addToCart(productId) {
  if (!(await requireLogin())) return;

  try {
    await api('/cart/items', {
      method: 'POST',
      body: JSON.stringify({ product_id: productId, quantity: 1 }),
    });
    await refreshCart();
    toast('Added to your cart');
  } catch (error) {
    toast(error.message);
  }
}

async function openCart() {
  if (!(await requireLogin())) return;
  await refreshCart();
  renderCart(changeQuantity, removeItem);
  openOverlay('#cartOverlay');
}

function closeCart() {
  closeOverlay('#cartOverlay');
}

async function changeQuantity(productId, quantity) {
  try {
    if (quantity <= 0) return removeItem(productId);

    const product = productById(productId);
    if (product && quantity > Number(product.stock)) {
      toast(`Only ${product.stock} available`);
      return;
    }

    await api(`/cart/items/${productId}`, {
      method: 'PATCH',
      body: JSON.stringify({ product_id: productId, quantity }),
    });
    await refreshCart();
    renderCart(changeQuantity, removeItem);
  } catch (error) {
    toast(error.message);
  }
}

async function removeItem(productId) {
  try {
    await api(`/cart/items/${productId}`, { method: 'DELETE' });
    await refreshCart();
    renderCart(changeQuantity, removeItem);
    toast('Item removed');
  } catch (error) {
    toast(error.message);
  }
}

function openCheckout() {
  if (!state.cart.items.length) {
    toast('Your cart is empty');
    return;
  }
  closeCart();
  renderCheckout(placeOrder);
  openOverlay('#checkoutOverlay');
}

function closeCheckout() {
  closeOverlay('#checkoutOverlay');
}

async function placeOrder(total) {
  const button = $('#placeOrder');
  button.disabled = true;
  button.textContent = 'Processing order…';

  try {
    const result = await api('/order/orders', {
      method: 'POST',
      body: JSON.stringify({
        customer_email: state.user.email,
        items: state.cart.items.map((item) => ({
          product_id: Number(item.product_id),
          quantity: Number(item.quantity),
        })),
        total: Number(total),
      }),
    });

    await api('/cart', { method: 'DELETE' });
    await refreshCart();
    closeCheckout();
    await refreshOrders();
    $('#orders').scrollIntoView({ behavior: 'smooth', block: 'start' });
    toast(`Order #${result.id} confirmed 🎉`);

    // Inventory changed after a successful order; refresh catalog stock.
    await loadProducts();
  } catch (error) {
    button.disabled = false;
    button.textContent = 'Place order';
    toast(error.message);
  }
}

function bindEvents() {
  $('#loginForm').addEventListener('submit', login);
  $('#registerForm').addEventListener('submit', register);
  $('#loginTab').addEventListener('click', () => setAuthMode('login'));
  $('#registerTab').addEventListener('click', () => setAuthMode('register'));

  $('#accountBtn').addEventListener('click', openLogin);
  $('#cartButton').addEventListener('click', openCart);
  $('#closeCart').addEventListener('click', closeCart);
  $('#checkoutButton').addEventListener('click', openCheckout);
  $('#closeAuth').addEventListener('click', closeAuth);
  $('#closeCheckout').addEventListener('click', closeCheckout);

  $('#authOverlay').addEventListener('click', (event) => {
    if (event.target === event.currentTarget) closeAuth();
  });
  $('#cartOverlay').addEventListener('click', (event) => {
    if (event.target === event.currentTarget) closeCart();
  });
  $('#checkoutOverlay').addEventListener('click', (event) => {
    if (event.target === event.currentTarget) closeCheckout();
  });

  $('#exploreButton').addEventListener('click', () => $('#shop').scrollIntoView({ behavior: 'smooth' }));
  $('#heroCartButton').addEventListener('click', openCart);
  $('#aboutButton').addEventListener('click', () => $('#shop').scrollIntoView({ behavior: 'smooth' }));

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    closeAuth();
    closeCart();
    closeCheckout();
  });
}

async function boot() {
  bindEvents();
  updateAccount(openLogin, logout);
  updateCartBadge();

  try {
    await loadProducts();
    await refreshSession();
  } catch (error) {
    console.error(error);
    $('#grid').innerHTML = '<div class="empty" style="grid-column:1/-1">Unable to load CloudCart right now. Please try again.</div>';
  }
}

boot();
