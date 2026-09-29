import { state, productById, cartQuantity, cartTotal } from './store.js';

export const $ = (selector) => document.querySelector(selector);
export const money = (value) => `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
export const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

let toastTimer;

export function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('show'), 2200);
}

export function setAuthMode(mode) {
  const login = mode === 'login';
  $('#loginTab').classList.toggle('active', login);
  $('#registerTab').classList.toggle('active', !login);
  $('#loginForm').classList.toggle('hidden', !login);
  $('#registerForm').classList.toggle('hidden', login);
  $('#authTitle').textContent = login ? 'Welcome back' : 'Create your account';
  $('#authSubtitle').textContent = login
    ? 'Sign in to sync your cart and view orders.'
    : 'Create an account and start shopping with CloudCart.';
}

export function renderFilters(onFilter) {
  const categories = ['All', ...new Set(state.products.map((product) => product.category))];
  $('#filters').innerHTML = categories.map((category) => `
    <button class="filter ${category === state.category ? 'active' : ''}" data-category="${escapeHtml(category)}" type="button">
      ${escapeHtml(category)}
    </button>`).join('');

  $('#filters').querySelectorAll('[data-category]').forEach((button) => {
    button.addEventListener('click', () => onFilter(button.dataset.category));
  });
}

export function renderProducts(onAdd) {
  const products = state.category === 'All'
    ? state.products
    : state.products.filter((product) => product.category === state.category);

  if (!products.length) {
    $('#grid').innerHTML = '<div class="empty" style="grid-column:1/-1">No products found.</div>';
    return;
  }

  $('#grid').innerHTML = products.map((product) => {
    const stock = Number(product.stock);
    const stockClass = stock <= 0 ? 'out' : stock <= 5 ? 'low' : '';
    const stockText = stock <= 0
      ? 'Out of stock'
      : stock <= 5
        ? `Only ${stock} left`
        : `In stock · ${stock} available`;

    return `
      <article class="card">
        <div class="pic">${escapeHtml(product.emoji || '📦')}</div>
        <div class="cat">${escapeHtml(product.category).toUpperCase()}</div>
        <h3>${escapeHtml(product.name)}</h3>
        <div class="desc">${escapeHtml(product.description)}</div>
        <div class="stock ${stockClass}">${stockText}</div>
        <div class="row">
          <span class="price">${money(product.price)}</span>
          <button class="add" data-product-id="${product.id}" type="button" ${stock <= 0 ? 'disabled' : ''}>Add to cart</button>
        </div>
      </article>`;
  }).join('');

  $('#grid').querySelectorAll('[data-product-id]').forEach((button) => {
    button.addEventListener('click', () => onAdd(Number(button.dataset.productId)));
  });
}

export function updateAccount(onLogin, onLogout) {
  const button = $('#accountBtn');
  if (state.user) {
    button.innerHTML = `<span class="user-name">${escapeHtml(state.user.email)}</span> · Sign out`;
    button.onclick = onLogout;
  } else {
    button.textContent = 'Sign in';
    button.onclick = onLogin;
  }
}

export function updateCartBadge() {
  $('#cartCount').textContent = cartQuantity();
}

export function renderCart(onChangeQuantity, onRemove) {
  const list = $('#cartList');

  if (!state.cart.items.length) {
    list.innerHTML = '<div class="empty">Your cart is empty.<br><br>Browse the collection and add something you like.</div>';
    $('#cartTotal').textContent = '₹0';
    $('#checkoutButton').disabled = true;
    return;
  }

  $('#checkoutButton').disabled = false;
  list.innerHTML = state.cart.items.map((item) => {
    const product = productById(item.product_id);
    if (!product) return '';
    const quantity = Number(item.quantity);
    const lineTotal = Number(product.price) * quantity;
    const maxStock = Number(product.stock);
    const canIncrease = quantity < maxStock;

    return `
      <div class="cart-item">
        <div class="thumb">${escapeHtml(product.emoji || '📦')}</div>
        <div>
          <h4>${escapeHtml(product.name)}</h4>
          <small>${money(product.price)} each</small>
          <div class="qty">
            <button data-quantity="${product.id}" data-value="${quantity - 1}" type="button" aria-label="Decrease quantity">−</button>
            <b>${quantity}</b>
            <button data-quantity="${product.id}" data-value="${quantity + 1}" type="button" aria-label="Increase quantity" ${canIncrease ? '' : 'disabled'}>+</button>
          </div>
        </div>
        <div class="cart-line-total">
          <b>${money(lineTotal)}</b><br>
          <button class="remove" data-remove="${product.id}" type="button">Remove</button>
        </div>
      </div>`;
  }).join('');

  list.querySelectorAll('[data-quantity]').forEach((button) => {
    button.addEventListener('click', () => onChangeQuantity(
      Number(button.dataset.quantity),
      Number(button.dataset.value),
    ));
  });

  list.querySelectorAll('[data-remove]').forEach((button) => {
    button.addEventListener('click', () => onRemove(Number(button.dataset.remove)));
  });

  $('#cartTotal').textContent = money(cartTotal());
}

export function renderCheckout(onPlaceOrder) {
  const total = cartTotal();

  $('#checkoutBody').innerHTML = `
    <div class="checkout-summary">
      ${state.cart.items.map((item) => {
        const product = productById(item.product_id);
        return product
          ? `<div class="checkout-line"><span>${escapeHtml(product.name)} × ${item.quantity}</span><b>${money(Number(product.price) * Number(item.quantity))}</b></div>`
          : '';
      }).join('')}
      <hr>
      <div class="checkout-total"><span>Total</span><span>${money(total)}</span></div>
    </div>
    <div class="payment-note">
      <strong>Secure demo checkout</strong>
      <span>Payment is simulated by the CloudCart Payment service. No real payment details are collected.</span>
    </div>
    <button class="pill primary full" id="placeOrder" type="button">Place order</button>`;

  $('#placeOrder').addEventListener('click', () => onPlaceOrder(total));
}

export function renderOrders(orders) {
  const section = $('#orders');

  if (!orders.length) {
    section.classList.remove('visible');
    return;
  }

  section.classList.add('visible');
  $('#ordersList').innerHTML = orders.map((order) => `
    <div class="order-card">
      <div>
        <b>Order #${order.id}</b>
        <div class="order-meta">${escapeHtml(order.customer_email)}</div>
      </div>
      <span class="status">${escapeHtml(order.status)}</span>
      <strong>${money(order.total)}</strong>
    </div>`).join('');
}
