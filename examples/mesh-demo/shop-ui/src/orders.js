import axios from "axios";

export const getOrder = (id) => axios.get(`http://orders-api/api/orders/${id}`);
export const placeOrder = (order) => axios.post("http://orders-api/api/orders", order);
