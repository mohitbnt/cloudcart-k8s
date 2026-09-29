export const state = {
  products: [],
  cart: { items: [] },
  user: null,
  category: 'All',
};

export function productById(id) {
  return state.products.find((product) => Number(product.id) === Number(id));
}

export function cartQuantity() {
  return state.cart.items.reduce((total, item) => total + Number(item.quantity), 0);
}

export function cartTotal() {
  return state.cart.items.reduce((total, item) => {
    const product = productById(item.product_id);
    return total + (product ? Number(product.price) * Number(item.quantity) : 0);
  }, 0);
}
