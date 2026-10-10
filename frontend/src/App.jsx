import { formatIST } from "./utils/dateTime";
import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { GoogleLogin } from "@react-oauth/google";
import "./App.css";

const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("solvix_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

const SERVICES = [
  { name: "Plumber", icon: "🔧", description: "Pipes, taps & water systems" },
  { name: "Electrician", icon: "⚡", description: "Wiring, switches & repairs" },
  { name: "Mechanic", icon: "🛠️", description: "Vehicle repair & maintenance" },
  { name: "Carpenter", icon: "🪚", description: "Furniture & woodwork" },
  { name: "Painter", icon: "🎨", description: "Painting & wall finishing" },
  { name: "Cleaner", icon: "🧹", description: "Home & office cleaning" },
  { name: "AC Technician", icon: "❄️", description: "AC service & repair" },
  { name: "Appliance Repair", icon: "��", description: "Home appliance repair" },
  { name: "Other", icon: "✨", description: "Other local services" },
];

const STATUSES = [
  "confirmed",
  "on_the_way",
  "arrived",
  "in_progress",
  "completed",
  "cancelled",
];

function getError(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    "Something went wrong. Please try again."
  );
}

function getUserId(user) {
  return user?.id || user?.user_id;
}

function getWorkerId(worker) {
  return worker?.id || worker?.worker_id;
}

function getWorkerLocation(worker) {
  const location = worker?.location;

  if (Array.isArray(location?.coordinates)) {
    return {
      longitude: location.coordinates[0],
      latitude: location.coordinates[1],
    };
  }

  return {
    latitude: location?.latitude ?? worker?.latitude,
    longitude: location?.longitude ?? worker?.longitude,
  };
}

function getRequestId(request) {
  return request?.id || request?._id || request?.request_id;
}

function statusLabel(value) {
  return String(value || "pending")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function App() {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("solvix_user") || "null");
    } catch {
      return null;
    }
  });

  const [page, setPage] = useState("home");
  const [authMode, setAuthMode] = useState("login");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");

  const [authForm, setAuthForm] = useState({
    name: "",
    email: "",
    password: "",
    phone: "",
    role: "customer",
  });

  const [coords, setCoords] = useState({
    latitude: "",
    longitude: "",
  });

  const [locationMessage, setLocationMessage] = useState("");
  const [radius, setRadius] = useState("10");
  const [selectedService, setSelectedService] = useState("Plumber");
  const [workers, setWorkers] = useState([]);
  const [requests, setRequests] = useState([]);

  // SOLVIX_NOTIFICATION_BELL_V1
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationsLoading, setNotificationsLoading] = useState(false);

  const [booking, setBooking] = useState({
    service: "Plumber",
    description: "",
  });

  const [workerProfile, setWorkerProfile] = useState({
    profession: "Plumber",
    skills: "Pipe repair, Tap repair",
    experience_years: "1",
    service_radius_km: "10",
    bio: "",
    availability: "available",
  });

  const [profileExists, setProfileExists] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);

  // SOLVIX_SUBSCRIPTION_CHECKOUT_V1
  const [subscriptionData, setSubscriptionData] = useState(null);
  const [subscriptionPlans, setSubscriptionPlans] = useState([]);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [checkoutPlan, setCheckoutPlan] = useState("");

  const [statusDrafts, setStatusDrafts] = useState({});

  const clearMessages = () => {
    setNotice("");
    setError("");
  };

  const flashError = (message) => {
    setError(
      typeof message === "string" ? message : "Please check the entered details."
    );
    setNotice("");
  };

  const flashNotice = (message) => {
    setNotice(message);
    setError("");
  };

  const checkBackend = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/health`, {
        timeout: 15000,
      });
      setBackendStatus(
        response.data?.status === "healthy" ? "online" : "degraded"
      );
    } catch {
      setBackendStatus("offline");
    }
  }, []);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  useEffect(() => {
    if (user) {
      setPage("dashboard");
    }
  }, []);

  // Load notifications immediately and refresh every 15 seconds.
  useEffect(() => {
    let active = true;

    const refreshNotifications = async () => {
      if (!user || !localStorage.getItem("solvix_token")) {
        if (active) {
          setNotifications([]);
          setUnreadCount(0);
        }
        return;
      }

      try {
        const response = await api.get("/api/notifications?limit=50");
        if (!active) return;

        setNotifications(response.data?.notifications || []);
        setUnreadCount(Number(response.data?.unread_count || 0));
      } catch {
        // Keep the dashboard usable if notifications are temporarily unavailable.
      }
    };

    refreshNotifications();
    const timer = window.setInterval(refreshNotifications, 15000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [user]);

  const markNotificationRead = async (notification) => {
    if (!notification?.id || notification.is_read) return;

    // Update the UI immediately; restore the server state if the request fails.
    setNotifications((old) =>
      old.map((item) =>
        item.id === notification.id ? { ...item, is_read: true } : item
      )
    );
    setUnreadCount((old) => Math.max(0, old - 1));

    try {
      await api.patch(
        `/api/notifications/${encodeURIComponent(notification.id)}/read`
      );
    } catch {
      setNotifications((old) =>
        old.map((item) =>
          item.id === notification.id ? { ...item, is_read: false } : item
        )
      );
      setUnreadCount((old) => old + 1);
      flashError("Could not mark the notification as read. Please try again.");
    }
  };

  const markAllNotificationsRead = async () => {
    const previousNotifications = notifications;
    const previousUnreadCount = unreadCount;

    setNotifications((old) =>
      old.map((item) => ({ ...item, is_read: true }))
    );
    setUnreadCount(0);

    try {
      await api.patch("/api/notifications/read-all");
    } catch {
      setNotifications(previousNotifications);
      setUnreadCount(previousUnreadCount);
      flashError("Could not mark notifications as read. Please try again.");
    }
  };

  const saveSession = (token, loggedInUser) => {
    localStorage.setItem("solvix_token", token);
    localStorage.setItem("solvix_user", JSON.stringify(loggedInUser));
    setUser(loggedInUser);
    setPage("dashboard");
    clearMessages();
  };

  const logout = () => {
    localStorage.removeItem("solvix_token");
    localStorage.removeItem("solvix_user");
    setUser(null);
    setPage("home");
    setWorkers([]);
    setRequests([]);
    setNotifications([]);
    setUnreadCount(0);
    setNotificationsOpen(false);
    setProfileExists(false);
    setCoords({ latitude: "", longitude: "" });
    flashNotice("You have been logged out successfully.");
  };

  const openAuth = (mode, role = "customer") => {
    clearMessages();
    setAuthMode(mode);
    setAuthForm((old) => ({ ...old, role }));
    setPage("auth");
  };

  const handleAuth = async (event) => {
    event.preventDefault();
    clearMessages();
    setLoading(true);

    try {
      if (authMode === "register") {
        await api.post("/api/auth/register", {
          name: authForm.name.trim(),
          email: authForm.email.trim(),
          password: authForm.password,
          phone: authForm.phone.trim() || undefined,
          role: authForm.role,
        });

        const loginResponse = await api.post("/api/auth/login", {
          email: authForm.email.trim(),
          password: authForm.password,
        });

        const token = loginResponse.data.access_token;
        const loggedInUser = loginResponse.data.user;

        if (!token || !loggedInUser) {
          throw new Error("Registration succeeded, but automatic login failed.");
        }

        saveSession(token, loggedInUser);
        flashNotice("Your SOLVIX account has been created successfully.");
      } else {
        const response = await api.post("/api/auth/login", {
          email: authForm.email.trim(),
          password: authForm.password,
        });

        if (!response.data.access_token || !response.data.user) {
          throw new Error("The server did not return a valid login session.");
        }

        saveSession(response.data.access_token, response.data.user);
        flashNotice("Welcome back to SOLVIX!");
      }
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    if (!credentialResponse?.credential) {
      flashError("Google did not return a sign-in credential.");
      return;
    }

    clearMessages();
    setLoading(true);

    try {
      const response = await api.post("/api/auth/google", {
        credential: credentialResponse.credential,
        role: authForm.role,
      });

      if (!response.data?.access_token || !response.data?.user) {
        throw new Error("The server did not return a valid login session.");
      }

      saveSession(response.data.access_token, response.data.user);
      flashNotice("You are signed in to SOLVIX with Google!");
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const getCoordinates = () => {
    clearMessages();
    setLocationMessage("");

    if (!navigator.geolocation) {
      setLocationMessage(
        "Your browser does not support geolocation. Enter coordinates manually."
      );
      return;
    }

    setLocationMessage("Requesting your location permission...");

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          latitude: String(position.coords.latitude),
          longitude: String(position.coords.longitude),
        });
        setLocationMessage("Location detected. You can edit the coordinates.");
      },
      (geoError) => {
        const messages = {
          1: "Location permission denied. Enter coordinates manually.",
          2: "Location unavailable. Try again or enter coordinates manually.",
          3: "Location request timed out. Please try again.",
        };
        setLocationMessage(
          messages[geoError.code] ||
            "Could not get your location. Enter coordinates manually."
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  };

  const validCoordinates = () => {
    const latitude = Number(coords.latitude);
    const longitude = Number(coords.longitude);

    if (
      coords.latitude.trim() === "" ||
      coords.longitude.trim() === "" ||
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180
    ) {
      flashError("Please enter valid latitude and longitude, or detect your location.");
      return null;
    }

    return { latitude, longitude };
  };

  const findWorkers = async (service = "") => {
    clearMessages();

    if (!user || user.role !== "customer") {
      flashError("Please log in as a customer to search for workers.");
      return;
    }

    const location = validCoordinates();
    if (!location) return;

    setLoading(true);

    try {
      const body = {
        ...location,
        radius_km: Number(radius) || 10,
      };

      const response = service
        ? await api.post("/api/workers/match", { ...body, service })
        : await api.post("/api/workers/nearby", body);

      const data = response.data;
      setWorkers(Array.isArray(data.workers) ? data.workers : []);
      setSelectedService(service || "");

      setPage("workers");

      if (!data.workers?.length) {
        flashNotice("No matching workers were found. Try a larger search radius.");
      } else {
        flashNotice(`${data.workers.length} worker(s) found.`);
      }
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const loadCustomerRequests = async () => {
    clearMessages();
    setLoading(true);

    try {
      const response = await api.get("/api/requests");
      setRequests(
        Array.isArray(response.data.requests) ? response.data.requests : []
      );
      setPage("requests");
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const createBooking = async (event) => {
    event.preventDefault();
    clearMessages();

    if (!user || user.role !== "customer") {
      flashError("Log in with a customer account to create a booking.");
      return;
    }

    const location = validCoordinates();
    if (!location) return;

    setLoading(true);

    try {
      await api.post("/api/requests", {
        service: booking.service,
        description: booking.description.trim() || undefined,
        ...location,
      });

      setBooking((old) => ({ ...old, description: "" }));
      flashNotice("Your service request has been created successfully.");
      await loadCustomerRequests();
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const loadWorkerRequests = async () => {
    clearMessages();
    setLoading(true);

    try {
      const response = await api.get("/api/requests/worker/my-requests");
      setRequests(
        Array.isArray(response.data.requests) ? response.data.requests : []
      );
      setPage("requests");
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  // SOLVIX_SUBSCRIPTION_CHECKOUT_V1
  const loadSubscription = async (showError = false) => {
    if (user?.role !== "worker") return;

    setSubscriptionLoading(true);

    try {
      const plansResponse = await api.get("/api/subscriptions/plans");
      setSubscriptionPlans(
        Array.isArray(plansResponse.data?.plans)
          ? plansResponse.data.plans
          : []
      );

      const subscriptionResponse = await api.get("/api/subscriptions/me");
      setSubscriptionData(subscriptionResponse.data);
    } catch (err) {
      if (showError) {
        flashError(getError(err));
      }
    } finally {
      setSubscriptionLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === "worker") {
      loadSubscription();
    } else {
      setSubscriptionData(null);
      setSubscriptionPlans([]);
    }
  }, [user]);

  const loadRazorpayCheckout = async () => {
    if (window.Razorpay) return true;

    const existingScript = document.querySelector(
      'script[src="https://checkout.razorpay.com/v1/checkout.js"]'
    );

    if (existingScript) {
      if (existingScript.dataset.loaded === "true" && window.Razorpay) {
        return true;
      }

      await new Promise((resolve, reject) => {
        existingScript.addEventListener("load", () => resolve(true), {
          once: true,
        });
        existingScript.addEventListener(
          "error",
          () => reject(new Error("Razorpay Checkout could not be loaded.")),
          { once: true }
        );
      });

      return Boolean(window.Razorpay);
    }

    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;

      script.onload = () => {
        script.dataset.loaded = "true";
        resolve(true);
      };

      script.onerror = () => {
        script.remove();
        reject(new Error("Razorpay Checkout could not be loaded."));
      };

      document.body.appendChild(script);
    });

    return Boolean(window.Razorpay);
  };

  const startSubscriptionCheckout = async (planName) => {
    if (user?.role !== "worker") {
      flashError("Please log in as a worker to purchase a subscription.");
      return;
    }

    clearMessages();
    setCheckoutPlan(planName);

    try {
      const checkoutReady = await loadRazorpayCheckout();

      if (!checkoutReady || !window.Razorpay) {
        throw new Error("Razorpay Checkout is unavailable. Please retry.");
      }

      const orderResponse = await api.post(
        "/api/subscriptions/create-order",
        { plan: planName }
      );

      const order = orderResponse.data;

      if (!order?.key_id || !order?.order_id || !order?.amount) {
        throw new Error("The server returned an incomplete payment order.");
      }

      await new Promise((resolve, reject) => {
        let finished = false;

        const finish = () => {
          if (finished) return false;
          finished = true;
          setCheckoutPlan("");
          return true;
        };

        const options = {
          key: order.key_id,
          amount: order.amount,
          currency: order.currency || "INR",
          name: "SOLVIX",
          description:
            planName === "yearly"
              ? "Worker yearly subscription"
              : "Worker monthly subscription",
          order_id: order.order_id,
          handler: async (payment) => {
            try {
              const verification = await api.post(
                "/api/subscriptions/verify-payment",
                {
                  razorpay_order_id: payment.razorpay_order_id,
                  razorpay_payment_id: payment.razorpay_payment_id,
                  razorpay_signature: payment.razorpay_signature,
                }
              );

              if (verification.data?.success) {
                if (finish()) {
                  flashNotice(
                    "Payment verified. Your subscription has been activated."
                  );
                  await loadSubscription();
                }
                resolve(true);
              } else {
                throw new Error(
                  "Payment verification was not confirmed by the server."
                );
              }
            } catch (err) {
              finish();
              flashError(
                "Payment was submitted, but verification is pending: " +
                  getError(err)
              );
              reject(err);
            }
          },
          modal: {
            ondismiss: () => {
              if (finish()) resolve(false);
            },
          },
          theme: {
            color: "#176b52",
          },
        };

        const checkout = new window.Razorpay(options);

        checkout.on("payment.failed", (event) => {
          if (finish()) {
            flashError(
              event?.error?.description ||
                "Payment failed. You can retry the checkout."
            );
            reject(
              new Error(
                event?.error?.description || "Razorpay payment failed."
              )
            );
          }
        });

        checkout.open();
      });
    } catch (err) {
      setCheckoutPlan("");
      if (err?.response || err?.message) {
        flashError(getError(err));
      }
    }
  };

  const loadWorkerProfile = async () => {
    clearMessages();
    setProfileLoading(true);

    try {
      const response = await api.get("/api/workers/profile");
      const profile = response.data?.profile || response.data?.worker || response.data;

      if (profile && profile.profession) {
        setWorkerProfile({
          profession: profile.profession || "Plumber",
          skills: Array.isArray(profile.skills)
            ? profile.skills.join(", ")
            : "",
          experience_years: String(profile.experience_years ?? 0),
          service_radius_km: String(profile.service_radius_km ?? 10),
          bio: profile.bio || "",
          availability: profile.availability || "available",
        });
        setProfileExists(true);

        const loc = getWorkerLocation(profile);
        if (
          Number.isFinite(Number(loc.latitude)) &&
          Number.isFinite(Number(loc.longitude))
        ) {
          setCoords({
            latitude: String(loc.latitude),
            longitude: String(loc.longitude),
          });
        }
      } else {
        setProfileExists(false);
      }

      setPage("profile");
    } catch (err) {
      if (err?.response?.status === 404) {
        setProfileExists(false);
        setPage("profile");
      } else {
        flashError(getError(err));
      }
    } finally {
      setProfileLoading(false);
    }
  };

  const saveWorkerProfile = async (event) => {
    event.preventDefault();
    clearMessages();
    setLoading(true);

    try {
      const payload = {
        profession: workerProfile.profession,
        skills: workerProfile.skills
          .split(",")
          .map((skill) => skill.trim())
          .filter(Boolean),
        experience_years: Number(workerProfile.experience_years),
        service_radius_km: Number(workerProfile.service_radius_km),
        bio: workerProfile.bio.trim() || undefined,
      };

      if (profileExists) {
        await api.patch("/api/workers/profile", payload);
      } else {
        await api.post("/api/workers/profile", payload);
        setProfileExists(true);
      }

      flashNotice("Worker profile saved successfully.");
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const saveAvailability = async (availability) => {
    clearMessages();
    setLoading(true);

    try {
      await api.patch("/api/workers/profile", { availability });
      setWorkerProfile((old) => ({ ...old, availability }));
      flashNotice(`Availability updated to ${availability}.`);
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const updateWorkerLocation = async () => {
    clearMessages();
    const location = validCoordinates();
    if (!location) return;

    setLoading(true);
    try {
      await api.patch("/api/workers/location", location);
      flashNotice("Your service location has been updated.");
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const workerAction = async (request, action) => {
    clearMessages();
    const requestId = getRequestId(request);

    if (!requestId) {
      flashError("The request ID is missing from the API response.");
      return;
    }

    setLoading(true);

    try {
      await api.patch(`/api/requests/${requestId}/worker-action`, { action });
      flashNotice(`Request ${action}ed successfully.`);
      await loadWorkerRequests();
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const updateRequestStatus = async (request) => {
    clearMessages();
    const requestId = getRequestId(request);
    const status = statusDrafts[requestId] || request.status;

    if (!requestId || !status) {
      flashError("Choose a valid request status.");
      return;
    }

    setLoading(true);

    try {
      await api.patch(`/api/requests/${requestId}/status`, { status });
      flashNotice("Request status updated.");
      if (user.role === "worker") await loadWorkerRequests();
      else await loadCustomerRequests();
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const autoMatch = async (request) => {
    clearMessages();
    const requestId = getRequestId(request);

    if (!requestId) {
      flashError("The request ID is missing from the API response.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.post(`/api/requests/${requestId}/match`);
      flashNotice(
        response.data?.message ||
          "Worker matching request processed successfully."
      );
      await loadCustomerRequests();
    } catch (err) {
      flashError(getError(err));
    } finally {
      setLoading(false);
    }
  };

  const goDashboard = () => {
    clearMessages();
    setPage("dashboard");
  };

  const updateAuthField = (event) => {
    setAuthForm((old) => ({
      ...old,
      [event.target.name]: event.target.value,
    }));
  };

  const serviceIcon = (service) =>
    SERVICES.find(
      (item) => item.name.toLowerCase() === String(service || "").toLowerCase()
    )?.icon || "🧰";

  const Header = () => (
    <header className="topbar">
      <button className="brand" onClick={() => setPage(user ? "dashboard" : "home")}>
        <span className="brand-mark">S</span>
        <span>SOLVIX<small>LOCAL SERVICES, SIMPLIFIED</small></span>
      </button>

      <nav className="nav-links">
        <button onClick={() => setPage(user ? "dashboard" : "home")}>Home</button>
        {user && (
          <button onClick={goDashboard}>Dashboard</button>
        )}
        {user?.role === "customer" && (
          <button onClick={loadCustomerRequests}>My bookings</button>
        )}
        {user?.role === "worker" && (
          <button onClick={loadWorkerRequests}>Service requests</button>
        )}
      </nav>

      <div className="nav-actions">
        {user ? (
          <>
            <div className="notification-control">
              <button
                type="button"
                className="notification-bell"
                aria-label={`Notifications, ${unreadCount} unread`}
                aria-expanded={notificationsOpen}
                title="Notifications"
                onClick={() => {
                  setNotificationsOpen((old) => !old);
                  if (!notificationsOpen) {
                    setNotificationsLoading(true);
                    api.get("/api/notifications?limit=50")
                      .then((response) => {
                        setNotifications(response.data?.notifications || []);
                        setUnreadCount(Number(response.data?.unread_count || 0));
                      })
                      .catch(() => {})
                      .finally(() => setNotificationsLoading(false));
                  }
                }}
              >
                <span aria-hidden="true">🔔</span>
                {unreadCount > 0 && (
                  <span className="notification-badge">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                )}
              </button>

              {notificationsOpen && (
                <section
                  className="notification-dropdown"
                  aria-label="Your notifications"
                >
                  <div className="notification-heading">
                    <div>
                      <strong>Notifications</strong>
                      <small>
                        {unreadCount} unread
                      </small>
                    </div>
                    {unreadCount > 0 && (
                      <button
                        type="button"
                        className="notification-mark-all"
                        onClick={markAllNotificationsRead}
                      >
                        Mark all read
                      </button>
                    )}
                  </div>

                  <div className="notification-list">
                    {notificationsLoading && notifications.length === 0 ? (
                      <p className="notification-empty">Loading notifications...</p>
                    ) : notifications.length === 0 ? (
                      <p className="notification-empty">
                        You're all caught up. New updates will appear here.
                      </p>
                    ) : (
                      notifications.map((notification) => (
                        <button
                          type="button"
                          key={notification.id}
                          className={`notification-item ${
                            notification.is_read ? "is-read" : "is-unread"
                          }`}
                          onClick={() => markNotificationRead(notification)}
                        >
                          <span className="notification-item-icon" aria-hidden="true">
                            {notification.is_read ? "✓" : "●"}
                          </span>
                          <span className="notification-item-content">
                            <strong>{notification.title}</strong>
                            <span>{notification.message}</span>
                            <small>
                              {notification.created_at
                                ? new Date(notification.created_at).toLocaleString(
                                    "en-IN",
                                    {
                                      day: "numeric",
                                      month: "short",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    }
                                  )
                                : ""}
                            </small>
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </section>
              )}
            </div>

            <span className="user-chip">
              <span className="avatar">{user.name?.charAt(0)?.toUpperCase() || "S"}</span>
              <span className="user-chip-text">
                {user.name}
                <small>{user.role}</small>
              </span>
            </span>
            <button className="btn btn-outline btn-small" onClick={logout}>Logout</button>
          </>
        ) : (
          <>
            <button className="btn btn-outline btn-small" onClick={() => openAuth("login")}>Log in</button>
            <button className="btn btn-primary btn-small" onClick={() => openAuth("register")}>Get started</button>
          </>
        )}
      </div>
    </header>
  );

  const Notice = () => (
    <>
      {notice && (
        <div className="notice success-notice">
          <span>✓</span><div>{notice}</div>
          <button onClick={() => setNotice("")} aria-label="Dismiss">×</button>
        </div>
      )}
      {error && (
        <div className="notice error-notice">
          <span>!</span><div>{String(error)}</div>
          <button onClick={() => setError("")} aria-label="Dismiss">×</button>
        </div>
      )}
    </>
  );

  const LocationPanel = () => (
    <section className="panel location-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">LOCATION SETTINGS</span>
          <h3>Where do you need help?</h3>
          <p>Use your current location or enter coordinates manually.</p>
        </div>
        <span className="location-icon">📍</span>
      </div>

      <button className="btn btn-outline geo-button" onClick={getCoordinates}>
        ◎ Detect my location
      </button>

      {locationMessage && <p className="helper-text">{locationMessage}</p>}

      <div className="form-grid two-columns">
        <label>
          Latitude
          <input
            type="number"
            step="any"
            placeholder="e.g. 28.6139"
            value={coords.latitude}
            onChange={(e) => setCoords((old) => ({ ...old, latitude: e.target.value }))}
          />
        </label>
        <label>
          Longitude
          <input
            type="number"
            step="any"
            placeholder="e.g. 77.2090"
            value={coords.longitude}
            onChange={(e) => setCoords((old) => ({ ...old, longitude: e.target.value }))}
          />
        </label>
      </div>

      <label className="field-label">
        Search radius
        <select value={radius} onChange={(e) => setRadius(e.target.value)}>
          <option value="2">2 km</option>
          <option value="5">5 km</option>
          <option value="10">10 km</option>
          <option value="20">20 km</option>
          <option value="50">50 km</option>
        </select>
      </label>
    </section>
  );

  const ServiceCards = () => (
    <div className="service-grid">
      {SERVICES.map((service) => (
        <button
          className="service-card"
          key={service.name}
          onClick={() => {
            setSelectedService(service.name);
            setBooking((old) => ({ ...old, service: service.name }));
            if (user?.role === "customer") {
              findWorkers(service.name);
            } else {
              openAuth("register", "customer");
            }
          }}
        >
          <span className="service-icon">{service.icon}</span>
          <strong>{service.name}</strong>
          <span>{service.description}</span>
          <span className="service-arrow">↗</span>
        </button>
      ))}
    </div>
  );

  const WorkerCard = ({ worker }) => {
    const loc = getWorkerLocation(worker);
    const workerId = getWorkerId(worker);
    const profession = worker.profession || "Local service professional";
    const skills = Array.isArray(worker.skills) ? worker.skills : [];

    return (
      <article className="worker-card" key={workerId || worker.user_id || profession}>
        <div className="worker-card-top">
          <div className="worker-avatar">{serviceIcon(profession)}</div>
          <div className="worker-title">
            <h3>{worker.name || worker.user?.name || profession}</h3>
            <p>{profession}</p>
          </div>
          <span className={`availability ${worker.availability === "available" ? "is-available" : ""}`}>
            {statusLabel(worker.availability || "available")}
          </span>
        </div>

        <div className="worker-metrics">
          <span>⭐ {Number(worker.rating || 0).toFixed(1)}</span>
          <span>🧰 {worker.experience_years || 0} yrs experience</span>
          <span>✓ {worker.completed_services || 0} jobs</span>
        </div>

        {skills.length > 0 && (
          <div className="skill-list">
            {skills.slice(0, 5).map((skill) => <span key={skill}>{skill}</span>)}
          </div>
        )}

        {worker.bio && <p className="worker-bio">{worker.bio}</p>}

        {(loc.latitude != null || loc.longitude != null) && (
          <p className="muted small-text">
            📍 {loc.latitude ?? "—"}, {loc.longitude ?? "—"}
          </p>
        )}

        {user?.role === "customer" && (
          <button
            className="btn btn-primary full-width"
            onClick={() => {
              setBooking((old) => ({ ...old, service: profession }));
              setPage("book");
            }}
          >
            Request this service →
          </button>
        )}
      </article>
    );
  };

  const RequestCard = ({ request }) => {
    const requestId = getRequestId(request);
    const currentStatus = request.status || "pending";
    const canWorkerAct =
      user?.role === "worker" &&
      (!request.worker_action || request.worker_action === "pending");

    return (
      <article className="request-card" key={requestId || JSON.stringify(request)}>
        <div className="request-heading">
          <div className="request-service-icon">{serviceIcon(request.service)}</div>
          <div className="request-title">
            <h3>{request.service || "Service request"}</h3>
            <p>Request ID: {requestId || "Not provided"}</p>
          </div>
          <span className={`status-badge status-${String(currentStatus).toLowerCase()}`}>
            {statusLabel(currentStatus)}
          </span>
        </div>

        {request.description && <p className="request-description">{request.description}</p>}

        <div className="request-details">
          {request.created_at && (
            <span>📅 {formatIST(request.created_at)}</span>
          )}
          {(request.latitude != null || request.longitude != null) && (
            <span>📍 {request.latitude ?? "—"}, {request.longitude ?? "—"}</span>
          )}
          {request.worker_id && <span>🧰 Worker assigned</span>}
        </div>

        {user?.role === "customer" && (
          <div className="request-actions">
            <button className="btn btn-outline" onClick={() => autoMatch(request)} disabled={loading}>
              Find a worker
            </button>
            <div className="status-control">
              <select
                value={statusDrafts[requestId] || currentStatus}
                onChange={(e) =>
                  setStatusDrafts((old) => ({ ...old, [requestId]: e.target.value }))
                }
              >
                {STATUSES.map((status) => (
                  <option key={status} value={status}>{statusLabel(status)}</option>
                ))}
              </select>
              <button className="btn btn-primary" onClick={() => updateRequestStatus(request)} disabled={loading}>
                Update
              </button>
            </div>
          </div>
        )}

        {canWorkerAct && (
          <div className="request-actions">
            <button className="btn btn-primary" onClick={() => workerAction(request, "accept")} disabled={loading}>
              ✓ Accept request
            </button>
            <button className="btn btn-danger-outline" onClick={() => workerAction(request, "reject")} disabled={loading}>
              ✕ Reject
            </button>
          </div>
        )}

        {user?.role === "worker" && (
          <div className="status-control worker-status-control">
            <select
              value={statusDrafts[requestId] || currentStatus}
              onChange={(e) =>
                setStatusDrafts((old) => ({ ...old, [requestId]: e.target.value }))
              }
            >
              {STATUSES.map((status) => (
                <option key={status} value={status}>{statusLabel(status)}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={() => updateRequestStatus(request)} disabled={loading}>
              Update status
            </button>
          </div>
        )}
      </article>
    );
  };

  const Dashboard = () => (
    <>
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="eyebrow light-eyebrow">
            {user?.role === "worker" ? "PROFESSIONAL WORKSPACE" : "YOUR PERSONAL WORKSPACE"}
          </span>
          <h1>
            {user?.role === "worker"
              ? `Welcome to your workspace, ${user?.name?.split(" ")[0] || "Professional"}.`
              : `Hello, ${user?.name?.split(" ")[0] || "there"}. What can we solve today?`}
          </h1>
          <p>
            {user?.role === "worker"
              ? "Manage your professional profile, availability and service requests."
              : "Find trusted local professionals and manage your service bookings."}
          </p>
          <span className="hero-status">
            <span className={`status-dot ${backendStatus === "online" ? "dot-online" : ""}`} />
            API {backendStatus === "online" ? "connected" : backendStatus}
          </span>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="art-circle circle-one" />
          <div className="art-circle circle-two" />
          <div className="art-card"><span>✓</span><div><strong>One place.</strong><small>Every solution.</small></div></div>
          <div className="art-tool">🧰</div>
        </div>
      </section>

      {user?.role === "customer" ? (
        <>
          <section className="section-block">
            <div className="section-heading">
              <div>
                <span className="eyebrow">WHAT DO YOU NEED?</span>
                <h2>Explore services</h2>
                <p>Choose a category to discover local professionals.</p>
              </div>
              <button className="text-button" onClick={() => setPage("services")}>View all services ↗</button>
            </div>
            {ServiceCards()}
          </section>

          <div className="dashboard-columns">
            {LocationPanel()}
            <section className="panel booking-panel">
              <span className="eyebrow">QUICK BOOKING</span>
              <h3>Tell us what you need</h3>
              <p>Submit your service request in a few simple steps.</p>
              <form onSubmit={createBooking}>
                <label>
                  Service category
                  <select
                    value={booking.service}
                    onChange={(e) => setBooking((old) => ({ ...old, service: e.target.value }))}
                  >
                    {SERVICES.map((service) => (
                      <option key={service.name} value={service.name}>{service.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Describe the problem
                  <textarea
                    rows="3"
                    maxLength="1000"
                    placeholder="Tell the professional what needs fixing..."
                    value={booking.description}
                    onChange={(e) => setBooking((old) => ({ ...old, description: e.target.value }))}
                  />
                </label>
                <button className="btn btn-primary full-width" type="submit" disabled={loading}>
                  {loading ? "Please wait..." : "Create service request →"}
                </button>
              </form>
            </section>
          </div>

          <section className="find-strip">
            <div><span className="eyebrow light-eyebrow">LOCAL PROFESSIONALS</span><h2>Find the right person for the job.</h2><p>Search using your location and preferred service radius.</p></div>
            <button className="btn btn-white" onClick={() => findWorkers()} disabled={loading}>Find nearby workers →</button>
          </section>
        </>
      ) : (
        <>
          <div className="dashboard-columns">
            <section className="panel">
              <span className="eyebrow">YOUR PROFESSIONAL PROFILE</span>
              <h2>Get discovered by customers.</h2>
              <p>Show your skills, experience and service area so customers can find you.</p>
              <button className="btn btn-primary" onClick={loadWorkerProfile} disabled={profileLoading}>
                {profileLoading ? "Loading..." : "Manage worker profile →"}
              </button>
            </section>

            <section className="panel">
              <span className="eyebrow">YOUR AVAILABILITY</span>
              <h3>Are you available for work?</h3>
              <p>Keep your status up to date so customers know when you can help.</p>
              <select
                value={workerProfile.availability}
                onChange={(e) => saveAvailability(e.target.value)}
                disabled={loading}
              >
                <option value="available">Available</option>
                <option value="busy">Busy</option>
                <option value="offline">Offline</option>
              </select>
              <div className="divider" />
              <button className="btn btn-outline" onClick={getCoordinates}>◎ Detect service location</button>
              {locationMessage && <p className="helper-text">{locationMessage}</p>}
              <div className="form-grid two-columns location-inputs">
                <label>Latitude<input type="number" step="any" value={coords.latitude} onChange={(e) => setCoords((old) => ({ ...old, latitude: e.target.value }))} placeholder="Latitude" /></label>
                <label>Longitude<input type="number" step="any" value={coords.longitude} onChange={(e) => setCoords((old) => ({ ...old, longitude: e.target.value }))} placeholder="Longitude" /></label>
              </div>
              <button className="btn btn-primary" onClick={updateWorkerLocation} disabled={loading}>Save service location</button>
            </section>
          </div>

          {/* SOLVIX_SUBSCRIPTION_CHECKOUT_V1 */}
          <section className="section-block">
            <div className="panel subscription-panel">
              <span className="eyebrow">SOLVIX PRO</span>
              <h2>Subscription &amp; free opportunities</h2>
              <p>
                Your first {subscriptionData?.free_opportunities?.total ?? 5}
                {" "}job opportunities are free. A paid plan gives you continued
                access to accepting jobs.
              </p>

              {subscriptionLoading && (
                <p role="status">Loading your subscription details...</p>
              )}

              {subscriptionData && (
                <div className="subscription-summary">
                  <div className="subscription-stat">
                    <span>Free opportunities remaining</span>
                    <strong>
                      {subscriptionData.free_opportunities?.remaining ?? 0}
                      {" / "}
                      {subscriptionData.free_opportunities?.total ?? 5}
                    </strong>
                  </div>

                  <div className="subscription-stat">
                    <span>Current plan</span>
                    <strong>
                      {subscriptionData.has_paid_access
                        ? statusLabel(subscriptionData.subscription?.plan)
                        : "Free plan"}
                    </strong>
                  </div>

                  {subscriptionData.subscription?.expires_at && (
                    <div className="subscription-stat">
                      <span>Subscription expires</span>
                      <strong>
                        {new Date(
                          subscriptionData.subscription.expires_at
                        ).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </strong>
                    </div>
                  )}
                </div>
              )}

              {!profileExists && (
                <p className="helper-text">
                  If you have not created your worker profile yet, create it
                  before purchasing a subscription.
                </p>
              )}

              <div className="subscription-plans">
                {subscriptionPlans.map((plan) => {
                  const planName = plan.plan;
                  const price =
                    plan.amount_rupees ??
                    (Number(plan.amount || 0) / 100);

                  return (
                    <article className="subscription-plan-card" key={planName}>
                      <span className="eyebrow">
                        {planName === "yearly" ? "BEST VALUE" : "FLEXIBLE"}
                      </span>
                      <h3>
                        {planName === "yearly" ? "Yearly plan" : "Monthly plan"}
                      </h3>
                      <p className="subscription-price">
                        ₹{Number(price).toLocaleString("en-IN")}
                        <span>
                          / {planName === "yearly" ? "year" : "month"}
                        </span>
                      </p>
                      <p>
                        {planName === "yearly"
                          ? "Access for 365 days."
                          : "Access for 30 days."}
                      </p>
                      <button
                        className="btn btn-primary full-width"
                        type="button"
                        disabled={
                          Boolean(checkoutPlan) ||
                          !profileExists ||
                          subscriptionLoading
                        }
                        onClick={() => startSubscriptionCheckout(planName)}
                      >
                        {checkoutPlan === planName
                          ? "Opening secure checkout..."
                          : `Choose ${planName} plan`}
                      </button>
                    </article>
                  );
                })}
              </div>

              <p className="helper-text">
                Payments are processed by Razorpay. Your paid access is
                activated only after server-side payment verification.
              </p>

              <button
                className="btn btn-outline"
                type="button"
                onClick={() => loadSubscription(true)}
                disabled={subscriptionLoading}
              >
                Refresh subscription status
              </button>
            </div>
          </section>

          <section className="section-block">
            <div className="section-heading">
              <div><span className="eyebrow">YOUR WORK</span><h2>Manage service requests</h2><p>Review requests and keep customers updated.</p></div>
              <button className="btn btn-primary" onClick={loadWorkerRequests}>View requests →</button>
            </div>
          </section>
        </>
      )}
    </>
  );

  const AuthPage = () => (
    <div className="auth-layout">
      <section className="auth-promo">
        <span className="eyebrow light-eyebrow">WELCOME TO SOLVIX</span>
        <h1>Good help.<br />Right around<br />the corner.</h1>
        <p>Connect with local professionals or grow your service business with SOLVIX.</p>
        <div className="promo-points">
          <span>✓ Simple, convenient service requests</span>
          <span>✓ Location-based worker discovery</span>
          <span>✓ One place to manage everything</span>
        </div>
        <div className="promo-decoration">S</div>
      </section>

      <section className="auth-form-wrap">
        <button className="back-link" onClick={() => setPage("home")}>← Back to home</button>
        <div className="auth-form-heading">
          <span className="eyebrow">{authMode === "login" ? "WELCOME BACK" : "GET STARTED"}</span>
          <h2>{authMode === "login" ? "Log in to SOLVIX" : "Create your account"}</h2>
          <p>{authMode === "login" ? "Enter your details to continue." : "Join your local service community."}</p>
        </div>

        <div className="auth-switch">
          <button className={authForm.role === "customer" ? "active" : ""} onClick={() => setAuthForm((old) => ({ ...old, role: "customer" }))}>I'm a customer</button>
          <button className={authForm.role === "worker" ? "active" : ""} onClick={() => setAuthForm((old) => ({ ...old, role: "worker" }))}>I'm a professional</button>
        </div>

        <form className="auth-form" onSubmit={handleAuth}>
          {authMode === "register" && (
            <label>Full name<input name="name" required minLength="2" maxLength="100" autoComplete="name" value={authForm.name} onChange={updateAuthField} placeholder="Your full name" /></label>
          )}
          <label>Email address<input type="email" name="email" required autoComplete="email" value={authForm.email} onChange={updateAuthField} placeholder="you@example.com" /></label>
          {authMode === "register" && (
            <label>Phone number <span className="optional">(optional)</span><input type="tel" name="phone" autoComplete="tel" value={authForm.phone} onChange={updateAuthField} placeholder="Your contact number" /></label>
          )}
          <label>Password<input type="password" name="password" required minLength="8" maxLength="128" autoComplete={authMode === "login" ? "current-password" : "new-password"} value={authForm.password} onChange={updateAuthField} placeholder="At least 8 characters" /></label>
          <button className="btn btn-primary full-width auth-submit" type="submit" disabled={loading}>
            {loading ? "Please wait..." : authMode === "login" ? "Log in →" : "Create account →"}
          </button>
        </form>

        {import.meta.env.VITE_GOOGLE_CLIENT_ID && (
          <div className="google-login-wrap" style={{ display: "flex", justifyContent: "center", margin: "18px 0" }}>
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={() => flashError("Google sign-in failed. Please try again.")}
              text={authMode === "login" ? "signin_with" : "signup_with"}
              shape="rectangular"
              theme="outline"
            />
          </div>
        )}

        <p className="auth-alternate">
          {authMode === "login" ? "New to SOLVIX?" : "Already have an account?"}
          <button onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); clearMessages(); }}>
            {authMode === "login" ? "Create an account" : "Log in"}
          </button>
        </p>
        <p className="auth-terms">By continuing, you agree to use SOLVIX responsibly and provide accurate account details.</p>
      </section>
    </div>
  );

  const ServicesPage = () => (
    <section className="section-block page-section">
      <button className="back-link" onClick={goDashboard}>← Back to dashboard</button>
      <span className="eyebrow">OUR CATEGORIES</span>
      <h1>Explore all services</h1>
      <p className="page-intro">Choose the service you need and find a professional near you.</p>
      {ServiceCards()}
    </section>
  );

  const WorkersPage = () => (
    <section className="section-block page-section">
      <button className="back-link" onClick={goDashboard}>← Back to dashboard</button>
      <div className="section-heading">
        <div><span className="eyebrow">LOCAL PROFESSIONALS</span><h1>{selectedService ? `${selectedService} professionals` : "Nearby workers"}</h1><p>Results returned by the SOLVIX worker discovery API.</p></div>
        <button className="btn btn-outline" onClick={() => findWorkers(selectedService)} disabled={loading}>Refresh results</button>
      </div>
      {workers.length ? (
        <div className="worker-grid">{workers.map((worker, index) => WorkerCard({ worker }))}</div>
      ) : (
        <div className="empty-state"><span>🔎</span><h3>No workers to display</h3><p>Try searching again or increase your radius.</p><button className="btn btn-primary" onClick={() => findWorkers(selectedService)} disabled={loading}>Search again</button></div>
      )}
    </section>
  );

  const RequestsPage = () => (
    <section className="section-block page-section">
      <button className="back-link" onClick={goDashboard}>← Back to dashboard</button>
      <div className="section-heading">
        <div><span className="eyebrow">{user?.role === "worker" ? "WORK QUEUE" : "YOUR ACTIVITY"}</span><h1>{user?.role === "worker" ? "Service requests" : "My bookings"}</h1><p>Review the current requests returned by the SOLVIX API.</p></div>
        <button className="btn btn-outline" onClick={user?.role === "worker" ? loadWorkerRequests : loadCustomerRequests} disabled={loading}>↻ Refresh</button>
      </div>
      {requests.length ? (
        <div className="request-list">{requests.map((request, index) => RequestCard({ request }))}</div>
      ) : (
        <div className="empty-state"><span>📋</span><h3>No requests yet</h3><p>Your service requests will appear here when available.</p>{user?.role === "customer" && <button className="btn btn-primary" onClick={() => setPage("book")}>Create a booking</button>}</div>
      )}
    </section>
  );

  const ProfilePage = () => (
    <section className="section-block page-section">
      <button className="back-link" onClick={goDashboard}>← Back to dashboard</button>
      <span className="eyebrow">PROFESSIONAL SETTINGS</span>
      <h1>Your worker profile</h1>
      <p className="page-intro">Add accurate information so customers can discover your services.</p>

      <form className="panel profile-form" onSubmit={saveWorkerProfile}>
        <label>Primary profession
          <select value={workerProfile.profession} onChange={(e) => setWorkerProfile((old) => ({ ...old, profession: e.target.value }))}>
            {SERVICES.map((service) => <option key={service.name} value={service.name}>{service.name}</option>)}
          </select>
        </label>
        <label>Skills <span className="optional">Separate skills with commas</span>
          <input value={workerProfile.skills} onChange={(e) => setWorkerProfile((old) => ({ ...old, skills: e.target.value }))} placeholder="Pipe repair, tap repair, installation" />
        </label>
        <div className="form-grid two-columns">
          <label>Years of experience
            <input type="number" min="0" max="80" required value={workerProfile.experience_years} onChange={(e) => setWorkerProfile((old) => ({ ...old, experience_years: e.target.value }))} />
          </label>
          <label>Service radius (km)
            <input type="number" min="1" max="200" required value={workerProfile.service_radius_km} onChange={(e) => setWorkerProfile((old) => ({ ...old, service_radius_km: e.target.value }))} />
          </label>
        </div>
        <label>About your services
          <textarea rows="5" maxLength="2000" value={workerProfile.bio} onChange={(e) => setWorkerProfile((old) => ({ ...old, bio: e.target.value }))} placeholder="Describe your experience and the services you provide." />
        </label>
        <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Saving..." : profileExists ? "Save profile changes →" : "Create worker profile →"}</button>
      </form>
    </section>
  );

  const BookingPage = () => (
    <section className="section-block page-section narrow-page">
      <button className="back-link" onClick={goDashboard}>← Back to dashboard</button>
      <span className="eyebrow">BOOK A PROFESSIONAL</span>
      <h1>What can we help you with?</h1>
      <p className="page-intro">Describe your service requirement and set your location.</p>
      {LocationPanel()}
      <form className="panel booking-form" onSubmit={createBooking}>
        <label>Service category
          <select value={booking.service} onChange={(e) => setBooking((old) => ({ ...old, service: e.target.value }))}>
            {SERVICES.map((service) => <option key={service.name} value={service.name}>{service.name}</option>)}
          </select>
        </label>
        <label>Describe the job
          <textarea rows="5" maxLength="1000" value={booking.description} onChange={(e) => setBooking((old) => ({ ...old, description: e.target.value }))} placeholder="What needs to be done?" />
        </label>
        <button className="btn btn-primary full-width" type="submit" disabled={loading}>{loading ? "Submitting..." : "Submit service request →"}</button>
      </form>
    </section>
  );

  return (
    <div className="app-shell">
      {Header()}

      <main className="main-content">
        {Notice()}

        {page === "auth" && AuthPage()}

        {page === "home" && (
          <>
            <section className="home-hero">
              <div className="home-hero-copy">
                <div className="hero-kicker"><span className="live-dot" /> YOUR NEIGHBOURHOOD, CONNECTED</div>
                <h1>Every problem has a <span>local solution.</span></h1>
                <p>From a leaking tap to a vehicle repair, discover skilled professionals around you and get things done without the hassle.</p>
                <div className="hero-buttons">
                  <button className="btn btn-primary btn-large" onClick={() => openAuth("register", "customer")}>Find a professional <span>→</span></button>
                  <button className="btn btn-outline btn-large" onClick={() => openAuth("register", "worker")}>Join as a professional</button>
                </div>
                <div className="hero-trust"><span className="trust-icon">✓</span><span>One platform</span><i /> <span>Local connections</span><i /> <span>Simple requests</span></div>
              </div>
              <div className="home-hero-visual" aria-hidden="true">
                <div className="visual-orbit orbit-one" />
                <div className="visual-orbit orbit-two" />
                <div className="visual-center">S<span>Connect. Solve.</span></div>
                <div className="float-bubble bubble-one"><span>🔧</span><div><strong>Home repairs</strong><small>Local professionals</small></div></div>
                <div className="float-bubble bubble-two"><span>⚡</span><div><strong>Quick solutions</strong><small>Right around you</small></div></div>
                <div className="float-bubble bubble-three"><span>🛠️</span><div><strong>Skilled workers</strong><small>Many services</small></div></div>
              </div>
            </section>

            <section className="home-stats">
              <div><strong>01</strong><span>Choose a service</span></div>
              <div><strong>02</strong><span>Set your location</span></div>
              <div><strong>03</strong><span>Connect and solve</span></div>
            </section>

            <section className="section-block">
              <div className="section-heading">
                <div><span className="eyebrow">SERVICES FOR EVERYDAY LIFE</span><h2>What do you need help with?</h2><p>Explore the services available through SOLVIX.</p></div>
                <button className="text-button" onClick={() => setPage("services")}>All categories ↗</button>
              </div>
              {ServiceCards()}
            </section>

            <section className="join-banner">
              <div><span className="eyebrow light-eyebrow">ARE YOU A SERVICE PROFESSIONAL?</span><h2>Turn your skills into opportunities.</h2><p>Create your professional profile and connect with customers in your service area.</p></div>
              <button className="btn btn-white" onClick={() => openAuth("register", "worker")}>Join SOLVIX →</button>
            </section>
          </>
        )}

        {page === "dashboard" && Dashboard()}
        {page === "services" && ServicesPage()}
        {page === "workers" && WorkersPage()}
        {page === "requests" && RequestsPage()}
        {page === "profile" && ProfilePage()}
        {page === "book" && BookingPage()}

        {loading && (
          <div className="loading-bar" role="status">
            <span /> Processing your request...
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="footer-brand"><span className="brand-mark">S</span><span>SOLVIX<small>Connect. Solve. Get It Done.</small></span></div>
        <p>Bringing local people and practical solutions closer together.</p>
        <div className="footer-bottom"><span>© {new Date().getFullYear()} SOLVIX</span><span className={`footer-api ${backendStatus === "online" ? "api-ok" : ""}`}><i /> API {backendStatus}</span></div>
      </footer>
    </div>
  );
}

export default App;
