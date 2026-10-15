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
  { name: "Appliance Repair", icon: "🔌", description: "Home appliance repair" },
  { name: "Teacher", icon: "📚", description: "School subjects & learning support" },
  { name: "Tutor", icon: "📝", description: "Personal and home tutoring" },
  { name: "Graphic Designer", icon: "🎨", description: "Logos, graphics & visual design" },
  { name: "Makeup Artist", icon: "💄", description: "Party, bridal & event makeup" },
  { name: "Beautician", icon: "💅", description: "Beauty and personal care" },
  { name: "Photographer", icon: "📸", description: "Events, portraits & photography" },
  { name: "Tailor", icon: "🧵", description: "Stitching, alterations & fitting" },
  { name: "Cook", icon: "👨‍🍳", description: "Home cooking and meal preparation" },
  { name: "Gardener", icon: "🌱", description: "Garden care & plant maintenance" },
  { name: "Fitness Trainer", icon: "🏋️", description: "Personal fitness and training" },
  { name: "Computer Repair", icon: "💻", description: "Computer setup & troubleshooting" },
  { name: "Pest Control", icon: "🛡️", description: "Pest inspection and control" },
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
  const detail =
    error?.response?.data?.detail ??
    error?.response?.data?.message ??
    error?.message;

  const toMessage = (value) => {
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
    if (Array.isArray(value)) {
      return value.map(toMessage).filter(Boolean).join(" ");
    }
    if (value && typeof value === "object") {
      if (typeof value.msg === "string") return value.msg;
      if (typeof value.message === "string") return value.message;
      try {
        return JSON.stringify(value);
      } catch {
        return "The server returned an unexpected error.";
      }
    }
    return "";
  };

  return toMessage(detail) || "Something went wrong. Please try again.";
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

function getRequestLocation(request) {
  const location = request?.location;

  if (Array.isArray(location?.coordinates) && location.coordinates.length >= 2) {
    const longitude = Number(location.coordinates[0]);
    const latitude = Number(location.coordinates[1]);

    if (
      Number.isFinite(latitude) &&
      Number.isFinite(longitude) &&
      latitude >= -90 && latitude <= 90 &&
      longitude >= -180 && longitude <= 180
    ) {
      return { latitude, longitude };
    }
  }

  if (request?.latitude != null && request?.longitude != null) {
    const latitude = Number(request.latitude);
    const longitude = Number(request.longitude);

    if (
      Number.isFinite(latitude) &&
      Number.isFinite(longitude) &&
      latitude >= -90 && latitude <= 90 &&
      longitude >= -180 && longitude <= 180
    ) {
      return { latitude, longitude };
    }
  }

  return null;
}

function notificationTypeLabel(eventType) {
  const labels = {
    booking_created: "New Service Request",
    booking_accepted: "Booking Accepted",
    booking_rejected: "Booking Declined",
    booking_confirmed: "Booking Confirmed",
    booking_on_the_way: "Worker On The Way",
    booking_arrived: "Worker Arrived",
    booking_in_progress: "Service Started",
    booking_completed: "Service Completed",
    booking_cancelled: "Booking Cancelled",
  };

  if (!eventType) return "Notification";

  return labels[eventType] ||
    String(eventType)
      .replace(/^booking_/, "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayDate(value) {
  if (!value) return "—";

  try {
    return formatIST(value);
  } catch (error) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";

    return date.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
    });
  }
}

const REQUEST_STATUS_OPTIONS = [
  "requested",
  "accepted",
  "confirmed",
  "on_the_way",
  "arrived",
  "in_progress",
  "completed",
  "cancelled",
  "rejected",
];

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
  // SOLVIX_EMAIL_OTP_PASSWORD_RESET_V1
  const [authStep, setAuthStep] = useState("credentials");
  const [authOtp, setAuthOtp] = useState("");

  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");

  // SOLVIX_LIVE_STATS_CONTACTS_ADMIN_V1
  const [publicStats, setPublicStats] = useState(null);
  const [requestContacts, setRequestContacts] = useState({});
  const [contactLoading, setContactLoading] = useState({});
  // SOLVIX_ADMIN_DASHBOARD_V2
  const [adminOverview, setAdminOverview] = useState(null);
  const [adminUsers, setAdminUsers] = useState([]);
  const [adminWorkers, setAdminWorkers] = useState([]);
  const [adminRequests, setAdminRequests] = useState([]);
  const [adminRecentRequests, setAdminRecentRequests] = useState([]);
  const [adminSubscriptions, setAdminSubscriptions] = useState([]);
  const [adminPayments, setAdminPayments] = useState([]);
  const [adminProfile, setAdminProfile] = useState(null);
  const [adminProfileLoading, setAdminProfileLoading] = useState(false);
  const [adminRequestFilters, setAdminRequestFilters] = useState({
    status: "",
    customer_id: "",
    worker_id: "",
    profession: "",
    start_date: "",
    end_date: "",
  });
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState("");

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

  // SOLVIX_FEEDBACK_RATINGS_V1
  const [reviewDrafts, setReviewDrafts] = useState({});
  const [reviewSubmitting, setReviewSubmitting] = useState({});
  const [workerReviews, setWorkerReviews] = useState([]);
  const [workerReviewsLoading, setWorkerReviewsLoading] = useState(false);

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

  // SOLVIX_PRIVATE_AADHAAR_VERIFICATION_UI_V1
  const [aadhaarStatus, setAadhaarStatus] = useState(null);
  const [aadhaarStatusLoading, setAadhaarStatusLoading] = useState(false);
  const [aadhaarUploadLoading, setAadhaarUploadLoading] = useState(false);
  const [aadhaarUploadError, setAadhaarUploadError] = useState("");
  const [aadhaarUploadMessage, setAadhaarUploadMessage] = useState("");
  const [aadhaarFile, setAadhaarFile] = useState(null);

  const [adminAadhaarItems, setAdminAadhaarItems] = useState([]);
  const [adminAadhaarFilter, setAdminAadhaarFilter] = useState("pending");
  const [adminAadhaarLoading, setAdminAadhaarLoading] = useState(false);
  const [adminAadhaarError, setAdminAadhaarError] = useState("");
  const [aadhaarPreview, setAadhaarPreview] = useState(null);
  const [aadhaarDecisionLoading, setAadhaarDecisionLoading] = useState({});
  const [aadhaarRejectionReasons, setAadhaarRejectionReasons] = useState({});

  const [adminNotifications, setAdminNotifications] = useState([]);
  const [adminUnreadCount, setAdminUnreadCount] = useState(0);
  const [adminNotificationsLoading, setAdminNotificationsLoading] = useState(false);
  const [adminNotificationError, setAdminNotificationError] = useState("");

  // SOLVIX_SUBSCRIPTION_CHECKOUT_V1
  const [subscriptionData, setSubscriptionData] = useState(null);
  const [subscriptionPlans, setSubscriptionPlans] = useState([]);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [checkoutPlan, setCheckoutPlan] = useState("");

  const [statusDrafts, setStatusDrafts] = useState({});

  // SOLVIX_PRO_DASHBOARD_PHONE_V1
  const [dashboardStats, setDashboardStats] = useState(null);
  const [dashboardStatsLoading, setDashboardStatsLoading] = useState(false);
  const [phoneInput, setPhoneInput] = useState(user?.phone || "");
  const [phoneSaving, setPhoneSaving] = useState(false);

  useEffect(() => {
    setPhoneInput(user?.phone || "");

    if (!user?.id || !["customer", "worker"].includes(user.role)) {
      setDashboardStats(null);
      return;
    }

    let cancelled = false;

    const loadStats = async () => {
      setDashboardStatsLoading(true);
      setDashboardStats(null);

      try {
        const endpoint =
          user.role === "worker"
            ? "/api/requests/worker/stats"
            : "/api/requests/customer/stats";

        const response = await api.get(endpoint);

        if (!cancelled && response.data?.success) {
          setDashboardStats(response.data);
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Could not load dashboard statistics:", err);
        }
      } finally {
        if (!cancelled) {
          setDashboardStatsLoading(false);
        }
      }
    };

    loadStats();

    return () => {
      cancelled = true;
    };
  }, [user?.id, user?.role]);

  useEffect(() => {
    let active = true;

    const refreshPublicStats = async () => {
      try {
        const response = await api.get("/api/stats/public", {
          timeout: 12000,
        });
        if (active && response.data?.success) {
          setPublicStats(response.data);
        }
      } catch {
        // Keep the homepage usable if the statistics API is unavailable.
      }
    };

    refreshPublicStats();
    const timer = window.setInterval(refreshPublicStats, 60000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

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

  // Load regular notifications and, for admins, admin-only notifications.
  // Both feeds appear in the same notification bell.
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
        const requests = [
          api.get("/api/notifications?limit=50"),
        ];

        if (user.role === "admin") {
          requests.push(api.get("/api/admin/notifications?limit=100"));
        }

        const responses = await Promise.all(requests);
        if (!active) return;

        const regularItems = (responses[0].data?.notifications || []).map(
          (item) => ({ ...item, notification_source: "regular" })
        );

        const adminItems = user.role === "admin"
          ? (responses[1].data?.items || []).map((item) => ({
              ...item,
              admin_notification_id: item.id,
              id: `admin:${item.id}`,
              notification_source: "admin",
            }))
          : [];

        const merged = [...regularItems, ...adminItems].sort(
          (a, b) =>
            new Date(b.created_at || 0).getTime() -
            new Date(a.created_at || 0).getTime()
        );

        setNotifications(merged);
        setUnreadCount(merged.filter((item) => !item.is_read).length);
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

    setNotifications((old) =>
      old.map((item) =>
        item.id === notification.id ? { ...item, is_read: true } : item
      )
    );
    setUnreadCount((old) => Math.max(0, old - 1));

    try {
      if (notification.notification_source === "admin") {
        await api.patch(
          `/api/admin/notifications/${encodeURIComponent(notification.admin_notification_id)}/read`
        );
      } else {
        await api.patch(
          `/api/notifications/${encodeURIComponent(notification.id)}/read`
        );
      }
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

  const openNotification = async (notification) => {
    setNotificationsOpen(false);
    clearMessages();

    await markNotificationRead(notification);

    const requestId = notification?.booking_id;

    if (!requestId) {
      flashNotice(notification?.message || "Notification opened.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.get(
        `/api/requests/${encodeURIComponent(requestId)}`
      );

      const request = response.data?.request;

      if (!request) {
        throw new Error("Request details were not returned by the server.");
      }

      setRequests((old) => {
        const existing = old.filter(
          (item) => getRequestId(item) !== getRequestId(request)
        );
        return [request, ...existing];
      });

      setPage("requests");
    } catch (err) {
      flashError(
        getError(err) || "Could not open this request. Please refresh your requests."
      );
    } finally {
      setLoading(false);
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

      if (user?.role === "admin") {
        await api.patch("/api/admin/notifications/read-all");
      }
    } catch {
      // Refresh from the server because one feed may already have been updated.
      try {
        const requests = [api.get("/api/notifications?limit=50")];

        if (user?.role === "admin") {
          requests.push(api.get("/api/admin/notifications?limit=100"));
        }

        const responses = await Promise.all(requests);
        const regularItems = (responses[0].data?.notifications || []).map(
          (item) => ({ ...item, notification_source: "regular" })
        );
        const adminItems = user?.role === "admin"
          ? (responses[1].data?.items || []).map((item) => ({
              ...item,
              admin_notification_id: item.id,
              id: `admin:${item.id}`,
              notification_source: "admin",
            }))
          : [];
        const merged = [...regularItems, ...adminItems].sort(
          (a, b) =>
            new Date(b.created_at || 0).getTime() -
            new Date(a.created_at || 0).getTime()
        );

        setNotifications(merged);
        setUnreadCount(merged.filter((item) => !item.is_read).length);
      } catch {
        setNotifications(previousNotifications);
        setUnreadCount(previousUnreadCount);
      }

      flashError("Some notifications could not be marked as read. Please try again.");
    }
  };

  const saveSession = (token, loggedInUser) => {
    localStorage.setItem("solvix_token", token);
    localStorage.setItem("solvix_user", JSON.stringify(loggedInUser));
    setUser(loggedInUser);
    setPage("dashboard");
    clearMessages();

    if (loggedInUser?.role === "worker") {
      api.get("/api/workers/profile")
        .then((response) => {
          const profile =
            response.data?.profile ||
            response.data?.worker ||
            response.data;

          if (profile?.profession) {
            setProfileExists(true);
            localStorage.removeItem("solvix_pending_profession");
            return;
          }

          const pendingProfession = localStorage.getItem(
            "solvix_pending_profession"
          );
          if (pendingProfession && SERVICES.some(
            (service) => service.name === pendingProfession
          )) {
            setWorkerProfile((old) => ({
              ...old,
              profession: pendingProfession,
            }));
          }

          setProfileExists(false);
          setPage("profile");
        })
        .catch((err) => {
          if (err?.response?.status === 404) {
            const pendingProfession = localStorage.getItem(
              "solvix_pending_profession"
            );
            if (pendingProfession && SERVICES.some(
              (service) => service.name === pendingProfession
            )) {
              setWorkerProfile((old) => ({
                ...old,
                profession: pendingProfession,
              }));
            }

            setProfileExists(false);
            setPage("profile");
          }
        });
    }
  };

  // SOLVIX_PRO_DASHBOARD_PHONE_V1
  const saveAccountPhone = async (event) => {
    event.preventDefault();
    clearMessages();

    const phone = phoneInput.trim();

    if (!/^[0-9]{10}$/.test(phone)) {
      flashError("Enter a valid 10-digit mobile number.");
      return;
    }

    setPhoneSaving(true);

    try {
      const response = await api.patch("/api/auth/phone", { phone });
      const updatedUser = response.data?.user;

      if (!updatedUser) {
        throw new Error("The server did not return the updated account.");
      }

      const nextUser = { ...user, ...updatedUser };
      localStorage.setItem("solvix_user", JSON.stringify(nextUser));
      setUser(nextUser);
      setPhoneInput(nextUser.phone || phone);
      flashNotice("Phone number saved successfully.");
    } catch (err) {
      flashError(getError(err) || "Could not save your phone number.");
    } finally {
      setPhoneSaving(false);
    }
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

    const email = authForm.email.trim().toLowerCase();

    try {
      if (authStep === "login-otp") {
        const response = await api.post("/api/auth/login/verify-otp", {
          email,
          otp: authOtp,
        });

        if (!response.data?.access_token || !response.data?.user) {
          throw new Error("OTP verification did not return a valid session.");
        }

        saveSession(response.data.access_token, response.data.user);
        setAuthOtp("");
        flashNotice("Email verified. Welcome back to SOLVIX!");
      } else if (authStep === "forgot") {
        await api.post("/api/auth/forgot-password", { email });

        setAuthStep("reset");
        setAuthOtp("");
        flashNotice(
          "If an account exists for this email, a password-reset code will be sent shortly."
        );
      } else if (authStep === "reset") {
        await api.post("/api/auth/reset-password", {
          email,
          otp: authOtp,
          new_password: authForm.password,
        });

        setAuthStep("credentials");
        setAuthMode("login");
        setAuthOtp("");
        setAuthForm((old) => ({ ...old, password: "" }));
        flashNotice("Password reset successfully. Please log in.");
      } else if (authMode === "register") {
        await api.post("/api/auth/register", {
          name: authForm.name.trim(),
          email,
          password: authForm.password,
          phone: authForm.phone.trim() || undefined,
          role: authForm.role,
        });

        setAuthMode("login");
        setAuthStep("credentials");
        setAuthForm((old) => ({
          ...old,
          name: "",
          password: "",
          phone: "",
        }));
        flashNotice("Account created successfully. Please log in to verify your email.");
      } else {
        const response = await api.post("/api/auth/login", {
          email,
          password: authForm.password,
        });

        if (!response.data?.access_token || !response.data?.user) {
          throw new Error("Login did not return a valid session.");
        }

        saveSession(response.data.access_token, response.data.user);
        setAuthOtp("");
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

  // SOLVIX_FEEDBACK_RATINGS_V1
  const submitReview = async (request) => {
    const requestId = getRequestId(request);
    const draft = reviewDrafts[requestId] || {
      rating: 5,
      feedback: "",
    };

    if (!requestId) {
      flashError("The booking ID is missing.");
      return;
    }

    if (!Number.isInteger(Number(draft.rating)) ||
        Number(draft.rating) < 1 ||
        Number(draft.rating) > 5) {
      flashError("Please select a rating from 1 to 5 stars.");
      return;
    }

    setReviewSubmitting((old) => ({ ...old, [requestId]: true }));

    try {
      const response = await api.post(
        `/api/requests/${encodeURIComponent(requestId)}/review`,
        {
          rating: Number(draft.rating),
          feedback: String(draft.feedback || "").trim(),
        }
      );

      setRequests((old) =>
        old.map((item) =>
          getRequestId(item) === requestId
            ? { ...item, review_submitted: true }
            : item
        )
      );

      setReviewDrafts((old) => ({
        ...old,
        [requestId]: { rating: 5, feedback: "" },
      }));

      flashNotice(
        response.data?.message || "Your review has been submitted."
      );

      // Refresh the worker cards so the latest average and review count
      // can be shown when the worker is listed again.
    } catch (err) {
      flashError(getError(err));
    } finally {
      setReviewSubmitting((old) => ({
        ...old,
        [requestId]: false,
      }));
    }
  };

  const loadWorkerReviews = async () => {
    if (user?.role !== "worker") return;

    setWorkerReviewsLoading(true);

    try {
      const response = await api.get("/api/requests/worker/my-reviews");
      setWorkerReviews(
        Array.isArray(response.data?.reviews) ? response.data.reviews : []
      );
    } catch (err) {
      console.error("Could not load worker reviews:", err);
    } finally {
      setWorkerReviewsLoading(false);
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

      // Automatically detect an existing worker profile after login.
      api.get("/api/workers/profile")
        .then((response) => {
          const profile =
            response.data?.profile ||
            response.data?.worker ||
            response.data;

          setProfileExists(Boolean(profile?.profession));
        })
        .catch((err) => {
          if (err?.response?.status === 404) {
            setProfileExists(false);
          }
        });
    } else {
      setSubscriptionData(null);
      setSubscriptionPlans([]);
      setProfileExists(false);
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

  // SOLVIX_PRIVATE_AADHAAR_VERIFICATION_UI_V1
  const loadWorkerAadhaarStatus = async () => {
    if (user?.role !== "worker") return;

    setAadhaarStatusLoading(true);
    setAadhaarUploadError("");

    try {
      const response = await api.get("/api/workers/aadhaar");
      setAadhaarStatus(response.data);
    } catch (err) {
      setAadhaarUploadError(getError(err));
    } finally {
      setAadhaarStatusLoading(false);
    }
  };

  const uploadWorkerAadhaar = async (event) => {
    event.preventDefault();
    setAadhaarUploadError("");
    setAadhaarUploadMessage("");

    if (!aadhaarFile) {
      setAadhaarUploadError("Please select your Aadhaar document first.");
      requestAnimationFrame(() => {
        const input = document.getElementById("worker-aadhaar-file");
        input?.scrollIntoView({ behavior: "smooth", block: "center" });
        input?.focus({ preventScroll: true });
      });
      return;
    }

    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
      "image/webp",
    ];

    if (!allowedTypes.includes(aadhaarFile.type)) {
      setAadhaarUploadError("Choose a PDF, JPEG, PNG, or WebP file.");
      return;
    }

    if (aadhaarFile.size > 10 * 1024 * 1024) {
      setAadhaarUploadError("Maximum file size is 10 MB.");
      return;
    }

    const formData = new FormData();
    formData.append("file", aadhaarFile);

    setAadhaarUploadLoading(true);
    try {
      const response = await api.post("/api/workers/aadhaar", formData);

      // The POST succeeded: report upload success even if refreshing status fails.
      setAadhaarUploadMessage(
        "Aadhaar document uploaded successfully. Waiting for admin verification."
      );
      setAadhaarUploadError("");
      setAadhaarFile(null);

      const input = document.getElementById("worker-aadhaar-file");
      if (input) input.value = "";

      try {
        const statusResponse = await api.get("/api/workers/aadhaar");
        setAadhaarStatus(statusResponse.data);
      } catch (statusError) {
        console.error("Upload succeeded, but Aadhaar status refresh failed:", statusError);
        setAadhaarUploadError(
          "Document uploaded successfully, but its latest status could not be refreshed. Please use Refresh or reload the page."
        );
      }
    } catch (err) {
      console.error("Aadhaar document upload failed:", err);
      setAadhaarUploadError(
        "Upload failed: " + getError(err)
      );
      setAadhaarUploadMessage("");
    } finally {
      setAadhaarUploadLoading(false);
    }
  };

  const loadAdminAadhaar = async (status = adminAadhaarFilter) => {
    if (user?.role !== "admin") return;

    setAdminAadhaarLoading(true);
    setAdminAadhaarError("");
    try {
      const response = await api.get(
        `/api/admin/aadhaar?status=${encodeURIComponent(status)}`
      );
      setAdminAadhaarItems(response.data?.items || []);
    } catch (err) {
      setAdminAadhaarError(getError(err));
    } finally {
      setAdminAadhaarLoading(false);
    }
  };

  const loadAdminNotifications = async () => {
    if (user?.role !== "admin") return;

    setAdminNotificationsLoading(true);
    setAdminNotificationError("");
    try {
      const response = await api.get("/api/admin/notifications?limit=100");
      setAdminNotifications(response.data?.items || []);
      setAdminUnreadCount(Number(response.data?.unread_count || 0));
    } catch (err) {
      setAdminNotificationError(getError(err));
    } finally {
      setAdminNotificationsLoading(false);
    }
  };

  const previewAdminAadhaar = async (item) => {
    if (user?.role !== "admin") return;

    try {
      const response = await api.get(
        `/api/admin/aadhaar/${encodeURIComponent(item.worker_id)}/document`,
        { responseType: "blob" }
      );

      const objectUrl = URL.createObjectURL(response.data);
      setAadhaarPreview((previous) => {
        if (previous?.url) URL.revokeObjectURL(previous.url);
        return {
          url: objectUrl,
          filename: item.filename || "Aadhaar document",
          contentType: item.content_type || response.data.type,
        };
      });
    } catch (err) {
      setAdminAadhaarError(getError(err));
    }
  };

  const closeAadhaarPreview = () => {
    setAadhaarPreview((previous) => {
      if (previous?.url) URL.revokeObjectURL(previous.url);
      return null;
    });
  };

  const decideAdminAadhaar = async (item, decision) => {
    if (user?.role !== "admin") return;

    const reason = (aadhaarRejectionReasons[item.worker_id] || "").trim();
    if (decision === "rejected" && !reason) {
      setAdminAadhaarError("Enter a rejection reason before rejecting this document.");
      return;
    }

    setAdminAadhaarError("");
    setAadhaarDecisionLoading((old) => ({
      ...old,
      [item.worker_id]: true,
    }));

    try {
      await api.post(
        `/api/admin/aadhaar/${encodeURIComponent(item.worker_id)}/decision`,
        {
          decision,
          ...(decision === "rejected" ? { rejection_reason: reason } : {}),
        }
      );

      setAdminAadhaarItems((old) =>
        old.filter((record) => record.worker_id !== item.worker_id)
      );
      setAadhaarRejectionReasons((old) => {
        const next = { ...old };
        delete next[item.worker_id];
        return next;
      });

      await Promise.all([
        loadAdminAadhaar(),
        loadAdminNotifications(),
      ]);
    } catch (err) {
      setAdminAadhaarError(getError(err));
    } finally {
      setAadhaarDecisionLoading((old) => ({
        ...old,
        [item.worker_id]: false,
      }));
    }
  };

  const markAdminNotificationRead = async (notification) => {
    if (user?.role !== "admin" || notification.is_read) return;

    try {
      await api.patch(
        `/api/admin/notifications/${encodeURIComponent(notification.id)}/read`
      );
      setAdminNotifications((old) =>
        old.map((item) =>
          item.id === notification.id
            ? { ...item, is_read: true }
            : item
        )
      );
      setAdminUnreadCount((count) => Math.max(0, count - 1));
    } catch (err) {
      setAdminNotificationError(getError(err));
    }
  };

  const markAllAdminNotificationsRead = async () => {
    if (user?.role !== "admin") return;

    try {
      await api.patch("/api/admin/notifications/read-all");
      setAdminNotifications((old) =>
        old.map((item) => ({ ...item, is_read: true }))
      );
      setAdminUnreadCount(0);
    } catch (err) {
      setAdminNotificationError(getError(err));
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

    const hasLatitude = coords.latitude.trim() !== "";
    const hasLongitude = coords.longitude.trim() !== "";
    let location = null;

    if (hasLatitude || hasLongitude) {
      location = validCoordinates();
      if (!location) return;
    } else if (!profileExists) {
      flashError(
        "Detect or enter your service location before creating your profile."
      );
      return;
    }

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

      if (location) {
        await api.patch("/api/workers/location", location);
      }

      localStorage.removeItem("solvix_pending_profession");
      flashNotice(
        location
          ? "Professional profile and service location saved successfully."
          : "Professional profile saved successfully."
      );
      setPage("dashboard");
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
      const errorMessage = getError(err);
      const requiresAadhaar =
        /aadhaar|identity document|document verification/i.test(errorMessage);

      if (requiresAadhaar && user?.role === "worker") {
        setAadhaarUploadMessage("");
        setAadhaarUploadError(errorMessage);
        setPage("profile");

        try {
          await loadWorkerProfile();
        } catch (profileError) {
          console.error("Could not load worker profile:", profileError);
        }

        setAadhaarUploadError(errorMessage);

        window.setTimeout(() => {
          const heading = document.getElementById("worker-aadhaar-heading");
          const input = document.getElementById("worker-aadhaar-file");

          heading?.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });

          if (input) {
            window.setTimeout(() => {
              input.focus({ preventScroll: true });
            }, 450);
          }
        }, 150);
      } else {
        flashError(errorMessage);
      }
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
      const response = await api.patch(
        `/api/requests/${requestId}/status`,
        { status }
      );

      const updatedRequest = response.data?.request;

      // Remove the old dropdown selection so the latest server status
      // is displayed after the request list refreshes.
      setStatusDrafts((old) => {
        const next = { ...old };
        delete next[requestId];
        return next;
      });

      if (updatedRequest) {
        setRequests((old) =>
          old.map((item) =>
            getRequestId(item) === requestId
              ? { ...item, ...updatedRequest }
              : item
          )
        );
      }

      flashNotice(
        response.data?.message || "Request status updated successfully."
      );

      if (user.role === "worker") {
        await loadWorkerRequests();
      } else {
        await loadCustomerRequests();
      }
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
      <button className="brand" onClick={() => setPage("home")}>
        <span className="brand-mark">S</span>
        <span>SOLVIX<small>LOCAL SERVICES, SIMPLIFIED</small></span>
      </button>

      <nav className="nav-links">
        <button onClick={() => setPage("home")}>Home</button>
        {user && (
          <button onClick={user.role === "admin" ? () => setPage("admin") : goDashboard}>
            {user.role === "admin" ? "Admin Dashboard" : "Dashboard"}
          </button>
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
                  const opening = !notificationsOpen;
                  setNotificationsOpen(opening);

                  if (opening) {
                    setNotificationsLoading(true);

                    const requests = [
                      api.get("/api/notifications?limit=50"),
                    ];

                    if (user?.role === "admin") {
                      requests.push(api.get("/api/admin/notifications?limit=100"));
                    }

                    Promise.all(requests)
                      .then((responses) => {
                        const regularItems = (
                          responses[0].data?.notifications || []
                        ).map((item) => ({
                          ...item,
                          notification_source: "regular",
                        }));

                        const adminItems = user?.role === "admin"
                          ? (responses[1].data?.items || []).map((item) => ({
                              ...item,
                              admin_notification_id: item.id,
                              id: `admin:${item.id}`,
                              notification_source: "admin",
                            }))
                          : [];

                        const merged = [...regularItems, ...adminItems].sort(
                          (a, b) =>
                            new Date(b.created_at || 0).getTime() -
                            new Date(a.created_at || 0).getTime()
                        );

                        setNotifications(merged);
                        setUnreadCount(
                          merged.filter((item) => !item.is_read).length
                        );
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
                          onClick={() => openNotification(notification)}
                        >
                          <span className="notification-item-icon" aria-hidden="true">
                            {notification.is_read ? "✓" : "●"}
                          </span>
                          <span className="notification-item-content">
                            <strong>{notification.title}</strong>
                            <span className="notification-type">
                              {notificationTypeLabel(notification.event_type)}
                            </span>
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
    <section
      id="service-location-panel"
      className="panel location-panel"
    >
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
              setPage("book");
              window.setTimeout(() => {
                document
                  .getElementById("service-location-panel")
                  ?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
              }, 150);
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
    const hasWorkerCoordinates =
      loc.latitude != null &&
      loc.longitude != null &&
      Number.isFinite(Number(loc.latitude)) &&
      Number.isFinite(Number(loc.longitude)) &&
      Number(loc.latitude) >= -90 &&
      Number(loc.latitude) <= 90 &&
      Number(loc.longitude) >= -180 &&
      Number(loc.longitude) <= 180;
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
          <span>
            ⭐ {Number(worker.rating || 0).toFixed(1)}
            {" · "}
            {Number(worker.total_reviews || 0)} reviews
          </span>
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

        {hasWorkerCoordinates && (
          <a
            className="btn btn-outline full-width"
            href={`https://www.google.com/maps/dir/?api=1&destination=${Number(loc.latitude)},${Number(loc.longitude)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            📍 Get Directions
          </a>
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

  const loadRequestContacts = async (request) => {
    const requestId = getRequestId(request);
    if (!requestId) {
      flashError("The booking ID is missing.");
      return;
    }

    setContactLoading((old) => ({ ...old, [requestId]: true }));
    try {
      const response = await api.get(
        `/api/requests/${encodeURIComponent(requestId)}/contacts`
      );
      setRequestContacts((old) => ({
        ...old,
        [requestId]: response.data?.contact || null,
      }));
      if (!response.data?.contact?.phone) {
        flashNotice("Contact loaded, but no phone number is available.");
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      flashError(
        typeof detail === "string"
          ? detail
          : getError(err)
      );
    } finally {
      setContactLoading((old) => ({ ...old, [requestId]: false }));
    }
  };

  const loadAdminData = async () => {
    if (user?.role !== "admin") {
      flashError("Admin access is required.");
      return;
    }

    setAdminLoading(true);
    setAdminError("");
    try {
      const [overview, users, workers, requests, subscriptions, payments] =
        await Promise.all([
          api.get("/api/admin/overview"),
          api.get("/api/admin/users?limit=100&page=1"),
          api.get("/api/admin/workers?limit=100&page=1"),
          api.get("/api/admin/requests?limit=100&page=1"),
          api.get("/api/admin/subscriptions?limit=100&page=1"),
          api.get("/api/admin/payments?limit=100&page=1"),
        ]);

      setAdminOverview(overview.data);
      setAdminUsers(users.data?.items || []);
      setAdminWorkers(workers.data?.items || []);
      setAdminRequests(requests.data?.items || []);
      setAdminRecentRequests(requests.data?.items || []);
      setAdminSubscriptions(subscriptions.data?.items || []);
      setAdminPayments(payments.data?.items || []);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setAdminError(
        typeof detail === "string"
          ? detail
          : getError(err)
      );
    } finally {
      setAdminLoading(false);
    }
  };

  const loadAdminProfile = async (kind, id) => {
    if (user?.role !== "admin" || !id) {
      flashError("Admin access is required.");
      return;
    }

    setAdminProfileLoading(true);
    setAdminProfile(null);
    setAdminError("");

    try {
      const endpoint =
        kind === "worker"
          ? `/api/admin/workers/${encodeURIComponent(id)}/details`
          : `/api/admin/customers/${encodeURIComponent(id)}/details`;

      const response = await api.get(endpoint);
      setAdminProfile({ kind, data: response.data });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setAdminError(
        typeof detail === "string" ? detail : getError(err)
      );
    } finally {
      setAdminProfileLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === "worker") {
      loadWorkerReviews();
    } else {
      setWorkerReviews([]);
    }
  }, [user?.id, user?.role]);

  useEffect(() => {
    if (page === "admin" && user?.role === "admin") {
      loadAdminData();
      loadAdminAadhaar();
      loadAdminNotifications();
    }
  }, [page, user?.role]);

  useEffect(() => {
    if (page === "profile" && user?.role === "worker") {
      loadWorkerAadhaarStatus();
    }
  }, [page, user?.role, user?.id]);

  useEffect(() => {
    return () => {
      if (aadhaarPreview?.url) URL.revokeObjectURL(aadhaarPreview.url);
    };
  }, [aadhaarPreview?.url]);

  const RequestCard = ({ request }) => {
    const requestId = getRequestId(request);
    const currentStatus = request.status || "pending";
    const requestLocation = getRequestLocation(request);
    const assignedWorkerId = request.assigned_worker_id;
    const currentWorkerId = getUserId(user);
    const isAssignedToCurrentWorker =
      Boolean(assignedWorkerId) &&
      String(assignedWorkerId) === String(currentWorkerId);
    const isAssignedToAnotherWorker =
      Boolean(assignedWorkerId) &&
      String(assignedWorkerId) !== String(currentWorkerId);

    const canWorkerAct =
      user?.role === "worker" &&
      !assignedWorkerId &&
      currentStatus === "requested" &&
      (!request.worker_action || request.worker_action === "pending");

    // Keep the dropdown aligned with backend status-transition rules.
    const allowedStatusTransitions = {
      requested: {
        customer: ["cancelled"],
        worker: [],
      },
      accepted: {
        customer: ["confirmed", "cancelled"],
        worker: ["cancelled", "rejected"],
      },
      confirmed: {
        customer: ["cancelled"],
        worker: ["on_the_way", "cancelled"],
      },
      on_the_way: {
        customer: ["cancelled"],
        worker: ["arrived", "cancelled"],
      },
      arrived: {
        customer: ["cancelled"],
        worker: ["in_progress", "cancelled"],
      },
      in_progress: {
        customer: ["cancelled"],
        worker: ["completed", "cancelled"],
      },
      completed: {
        customer: [],
        worker: [],
      },
      cancelled: {
        customer: [],
        worker: [],
      },
      rejected: {
        customer: [],
        worker: [],
      },
    };

    const canManageRequestStatus =
      user?.role === "customer" ||
      (user?.role === "worker" && isAssignedToCurrentWorker);

    const availableStatuses = canManageRequestStatus
      ? (allowedStatusTransitions[currentStatus]?.[user.role] || [])
      : [];

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
          {requestLocation && (
            <>
              <span>
                📍 {requestLocation.latitude.toFixed(6)},{" "}
                {requestLocation.longitude.toFixed(6)}
              </span>
              <a
                className="text-button"
                href={`https://www.google.com/maps/dir/?api=1&destination=${requestLocation.latitude},${requestLocation.longitude}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open location in Google Maps ↗
              </a>
            </>
          )}
          {assignedWorkerId && <span>🧰 Worker assigned</span>}
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
                <option value={currentStatus} disabled>
                  Current: {statusLabel(currentStatus)}
                </option>
                {availableStatuses.filter((status) => status !== currentStatus).map((status) => (
                  <option key={status} value={status}>
                    {statusLabel(status)}
                  </option>
                ))}
              </select>
              <button className="btn btn-primary" onClick={() => updateRequestStatus(request)} disabled={loading || availableStatuses.length === 0}>
                Update
              </button>
            </div>
          </div>
        )}

        {(
          (user?.role === "customer" && assignedWorkerId) ||
          (
            user?.role === "worker" &&
            String(assignedWorkerId || "") === String(getUserId(user) || "")
          )
        ) && (
          <div className="booking-contact-panel">
            {!requestContacts[requestId] ? (
              <button
                type="button"
                className="btn btn-outline"
                disabled={Boolean(contactLoading[requestId])}
                onClick={() => loadRequestContacts(request)}
              >
                {contactLoading[requestId]
                  ? "Loading contact..."
                  : "View booking contact"}
              </button>
            ) : (
              <div className="booking-contact-details">
                <strong>{requestContacts[requestId].name}</strong>
                {requestContacts[requestId].phone ? (
                  <a
                    className="btn btn-primary"
                    href={`tel:${String(requestContacts[requestId].phone).replace(/[^+\d]/g, "")}`}
                  >
                    Call {requestContacts[requestId].name}
                  </a>
                ) : (
                  <span>Phone number not available.</span>
                )}
              </div>
            )}
          </div>
        )}

        {/* SOLVIX_FEEDBACK_RATINGS_V1 */}
        {user?.role === "customer" &&
          currentStatus === "completed" &&
          assignedWorkerId &&
          (
            request.review_submitted ? (
              <div className="review-submitted" role="status">
                <strong>✓ Review submitted</strong>
                <p>Thank you for sharing your experience.</p>
              </div>
            ) : (
              <form
                className="review-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  submitReview(request);
                }}
              >
                <h4>Rate your service</h4>
                <p className="muted small-text">
                  Share your experience with this professional.
                </p>

                <div className="review-star-picker" aria-label="Choose a rating">
                  {[1, 2, 3, 4, 5].map((star) => {
                    const selectedRating = Number(
                      reviewDrafts[requestId]?.rating ?? 5
                    );

                    return (
                      <button
                        key={star}
                        type="button"
                        className={
                          star <= selectedRating
                            ? "review-star is-selected"
                            : "review-star"
                        }
                        aria-label={`${star} star${star === 1 ? "" : "s"}`}
                        aria-pressed={star === selectedRating}
                        onClick={() =>
                          setReviewDrafts((old) => ({
                            ...old,
                            [requestId]: {
                              rating: star,
                              feedback: old[requestId]?.feedback || "",
                            },
                          }))
                        }
                      >
                        ★
                      </button>
                    );
                  })}
                </div>

                <label>
                  Written feedback (optional)
                  <textarea
                    rows={3}
                    maxLength={1000}
                    placeholder="How was your experience?"
                    value={reviewDrafts[requestId]?.feedback || ""}
                    onChange={(event) =>
                      setReviewDrafts((old) => ({
                        ...old,
                        [requestId]: {
                          rating: old[requestId]?.rating ?? 5,
                          feedback: event.target.value,
                        },
                      }))
                    }
                  />
                </label>

                <button
                  className="btn btn-primary"
                  type="submit"
                  disabled={Boolean(reviewSubmitting[requestId])}
                >
                  {reviewSubmitting[requestId]
                    ? "Submitting review..."
                    : "Submit review"}
                </button>
              </form>
            )
          )}

        {user?.role === "worker" && isAssignedToAnotherWorker && (
          <div className="request-notice" role="status">
            <strong>Accepted by another worker</strong>
            <p>This request has already been assigned. You cannot accept or update it.</p>
          </div>
        )}

        {user?.role === "worker" && isAssignedToCurrentWorker && (
          <div className="request-notice" role="status">
            <strong>✓ This request is assigned to you</strong>
          </div>
        )}

        {canWorkerAct && (
          <div className="request-actions">
            <button
              className="btn btn-primary"
              onClick={() => workerAction(request, "accept")}
              disabled={loading}
            >
              ✓ Accept request
            </button>
            <button
              className="btn btn-danger-outline"
              onClick={() => workerAction(request, "reject")}
              disabled={loading}
            >
              ✕ Reject
            </button>
          </div>
        )}

        {user?.role === "worker" && isAssignedToCurrentWorker && availableStatuses.length > 0 && (
          <div className="status-control worker-status-control">
            <select
              value={statusDrafts[requestId] || currentStatus}
              onChange={(e) =>
                setStatusDrafts((old) => ({ ...old, [requestId]: e.target.value }))
              }
            >
              <option value={currentStatus} disabled>
                Current: {statusLabel(currentStatus)}
              </option>
              {availableStatuses.filter((status) => status !== currentStatus).map((status) => (
                <option key={status} value={status}>{statusLabel(status)}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={() => updateRequestStatus(request)} disabled={loading || availableStatuses.length === 0}>
              Update status
            </button>
          </div>
        )}
      </article>
    );
  };

  const AdminPage = () => {
    const overview = adminOverview || {};
    const userCounts = overview.users || {};
    const workerCounts = overview.workers || {};
    const requestCounts = overview.requests || {};
    const subscriptionCounts = overview.subscriptions || {};
    const paymentCounts = overview.payments || {};

    if (user?.role !== "admin") {
      return (
        <section className="section-block">
          <h1>Access denied</h1>
          <p>This page is available to authorized administrators only.</p>
          <button className="btn btn-primary" onClick={goDashboard}>
            Back to dashboard
          </button>
        </section>
      );
    }

    const Metric = ({ label, value }) => (
      <article className="dashboard-metric">
        <span>{label}</span>
        <strong>{Number(value || 0).toLocaleString()}</strong>
      </article>
    );

    const displayDate = (value) =>
      value ? formatIST(value) : "—";

    const displayAmount = (value) => {
      if (value === null || value === undefined || value === "") {
        return "—";
      }
      return `₹${(Number(value) / 100).toLocaleString("en-IN", {
        maximumFractionDigits: 2,
        minimumFractionDigits: 2,
      })}`;
    };

    const applyFilters = async () => {
      setAdminLoading(true);
      setAdminError("");

      try {
        const params = {
          page: 1,
          limit: 100,
        };

        Object.entries(adminRequestFilters).forEach(([key, value]) => {
          if (value) {
            params[key] = value;
          }
        });

        if (
          adminRequestFilters.start_date &&
          adminRequestFilters.end_date &&
          adminRequestFilters.start_date > adminRequestFilters.end_date
        ) {
          setAdminError("Start date must not be later than end date.");
          return;
        }

        if (params.start_date) {
          params.start_date = `${params.start_date}T00:00:00`;
        }
        if (params.end_date) {
          params.end_date = `${params.end_date}T23:59:59`;
        }

        const response = await api.get("/api/admin/requests/filter", {
          params,
        });

        setAdminRequests(response.data?.items || []);
      } catch (err) {
        const detail = err.response?.data?.detail;
        setAdminError(
          typeof detail === "string" ? detail : getError(err)
        );
      } finally {
        setAdminLoading(false);
      }
    };

    const clearFilters = async () => {
      setAdminRequestFilters({
        status: "",
        customer_id: "",
        worker_id: "",
        profession: "",
        start_date: "",
        end_date: "",
      });
      setAdminLoading(true);
      setAdminError("");

      try {
        const response = await api.get("/api/admin/requests", {
          params: { page: 1, limit: 100 },
        });
        setAdminRequests(response.data?.items || []);
      } catch (err) {
        setAdminError(getError(err));
      } finally {
        setAdminLoading(false);
      }
    };

    const profileData = adminProfile?.data;
    const profilePerson =
      adminProfile?.kind === "worker"
        ? profileData?.user
        : profileData?.customer;

    const profileJobs =
      adminProfile?.kind === "worker"
        ? profileData?.jobs
        : profileData?.requests;

    const toggleAdminSection = (id) => {
      const target = document.getElementById(id);
      if (!target) return;

      const panel = target.closest("details");
      if (!panel) return;

      panel.open = !panel.open;

      if (panel.open) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };

    return (
      <>
      <section className="section-block admin-dashboard">
        <div className="section-heading">
          <div>
            <span className="eyebrow">SOLVIX CONTROL CENTRE</span>
            <h1>Admin dashboard</h1>
            <p>Protected marketplace management and operational records.</p>
          </div>
          <button
            className="btn btn-outline"
            onClick={loadAdminData}
            disabled={adminLoading}
          >
            {adminLoading ? "Refreshing..." : "Refresh data"}
          </button>
        </div>

        {adminError && (
          <div className="notice notice-error" role="alert">
            {adminError}
          </div>
        )}

        {adminLoading && !adminOverview && <p>Loading admin data...</p>}

        {adminOverview && (
          <>
            <h2>Quick access</h2>
            <p className="admin-section-hint">
              Select a card to open or close its section.
            </p>
            <div className="admin-section-cards">
              <button
                type="button"
                className="admin-section-card"
                onClick={() => toggleAdminSection("admin-customers-section")}
              >
                <span className="admin-section-icon" aria-hidden="true">👥</span>
                <span className="admin-section-label">Customers</span>
                <strong>{Number(userCounts.customers ?? 0).toLocaleString()}</strong>
                <span className="admin-section-action">View customer directory →</span>
              </button>

              <button
                type="button"
                className="admin-section-card"
                onClick={() => toggleAdminSection("admin-workers-section")}
              >
                <span className="admin-section-icon" aria-hidden="true">🛠️</span>
                <span className="admin-section-label">Workers</span>
                <strong>{Number(workerCounts.total ?? adminWorkers.length).toLocaleString()}</strong>
                <span className="admin-section-action">View worker directory →</span>
              </button>

              <button
                type="button"
                className="admin-section-card"
                onClick={() => toggleAdminSection("admin-subscriptions-section")}
              >
                <span className="admin-section-icon" aria-hidden="true">💳</span>
                <span className="admin-section-label">Subscription records</span>
                <strong>{adminSubscriptions.length.toLocaleString()}</strong>
                <span className="admin-section-action">View subscriptions →</span>
              </button>

              <button
                type="button"
                className="admin-section-card"
                onClick={() => toggleAdminSection("admin-requests-section")}
              >
                <span className="admin-section-icon" aria-hidden="true">📋</span>
                <span className="admin-section-label">Service requests</span>
                <strong>{Number(requestCounts.total ?? adminRequests.length).toLocaleString()}</strong>
                <span className="admin-section-action">View requests →</span>
              </button>

              <button
                type="button"
                className="admin-section-card"
                onClick={() => toggleAdminSection("admin-payments-section")}
              >
                <span className="admin-section-icon" aria-hidden="true">💰</span>
                <span className="admin-section-label">Payment records</span>
                <strong>{adminPayments.length.toLocaleString()}</strong>
                <span className="admin-section-action">View payments →</span>
              </button>
            </div>

            <details className="admin-collapsible">
              <summary>Marketplace overview</summary>
            <div className="admin-metrics">
              <Metric label="All users" value={userCounts.total} />
              <Metric label="Customers" value={userCounts.customers} />
              <Metric label="Workers" value={userCounts.workers} />
              <Metric label="Active accounts" value={userCounts.active} />
              <Metric label="All requests" value={requestCounts.total} />
              <Metric label="Completed jobs" value={requestCounts.completed} />
              <Metric label="Active subscriptions" value={subscriptionCounts.active} />
              <Metric label="Verified payments" value={paymentCounts.verified} />
            </div>

            </details>

            <details className="admin-collapsible">
              <summary>Worker availability</summary>
            <div className="admin-metrics">
              <Metric label="Registered workers" value={workerCounts.total} />
              <Metric label="Available" value={workerCounts.available} />
              <Metric label="Busy" value={workerCounts.busy} />
            </div>

            </details>

            <details className="admin-collapsible">
              <summary>Request status summary</summary>
            <div className="admin-metrics">
              <Metric label="Requested" value={requestCounts.requested} />
              <Metric label="Accepted" value={requestCounts.accepted} />
              <Metric label="In progress" value={requestCounts.in_progress} />
              <Metric label="Completed" value={requestCounts.completed} />
              <Metric label="Cancelled" value={requestCounts.cancelled} />
            </div>

            </details>

            <details className="admin-collapsible">
              <summary id="admin-customers-section" className="admin-section-anchor">Customer directory</summary>
            <p>Select a customer or worker to inspect their available records.</p>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Active</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {adminUsers.filter((item) => item.role === "customer").map((item) => (
                    <tr key={item.id}>
                      <td>{item.name || "—"}</td>
                      <td>{item.email || "—"}</td>
                      <td>{item.phone || "—"}</td>
                      <td>{item.is_active ? "Yes" : "No"}</td>
                      <td>
                        {item.role === "customer" ? (
                          <button
                            className="btn btn-outline admin-small-button"
                            onClick={() => loadAdminProfile("customer", item.id)}
                          >
                            View customer
                          </button>
                        ) : item.role === "worker" ? (
                          <button
                            className="btn btn-outline admin-small-button"
                            onClick={() => {
                              const worker = adminWorkers.find(
                                (entry) => String(entry.user_id) === String(item.id)
                              );
                              loadAdminProfile("worker", worker?.id || item.id);
                            }}
                          >
                            View worker
                          </button>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                  {!adminUsers.length && (
                    <tr><td colSpan="5">No customers returned.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {adminProfileLoading && <p>Loading profile details...</p>}

            {profileData && (
              <section className="admin-profile-panel">
                <div className="admin-profile-heading">
                  <div>
                    <span className="eyebrow">PROFILE DETAILS</span>
                    <h2>
                      {adminProfile.kind === "worker" ? "Worker profile" : "Customer profile"}
                    </h2>
                  </div>
                  <button
                    className="btn btn-outline"
                    onClick={() => setAdminProfile(null)}
                  >
                    Close
                  </button>
                </div>

                <div className="admin-profile-grid">
                  <div><span>Name</span><strong>{profilePerson?.name || "—"}</strong></div>
                  <div><span>Email</span><strong>{profilePerson?.email || "—"}</strong></div>
                  <div><span>Phone</span><strong>{profilePerson?.phone || "—"}</strong></div>
                  {adminProfile.kind === "worker" && (
                    <>
                      <div><span>Profession</span><strong>{profileData.worker?.profession || "—"}</strong></div>
                      <div><span>Skills</span><strong>{Array.isArray(profileData.worker?.skills) ? profileData.worker.skills.join(", ") : profileData.worker?.skills || "—"}</strong></div>
                      <div><span>Experience</span><strong>{profileData.worker?.experience_years ?? "—"} years</strong></div>
                      <div><span>Availability</span><strong>{statusLabel(profileData.worker?.availability)}</strong></div>
                      <div><span>Rating</span><strong>{Number(profileData.worker?.rating || 0).toFixed(1)} ({profileData.worker?.total_reviews || 0} reviews)</strong></div>
                      <div>
                        <span>Location coordinates</span>
                        <strong>
                          {Array.isArray(profileData.worker?.location?.coordinates)
                            ? `${profileData.worker.location.coordinates[1]}, ${profileData.worker.location.coordinates[0]}`
                            : "Not available"}
                        </strong>
                      </div>
                      <div>
                        <span>Service radius</span>
                        <strong>
                          {profileData.worker?.service_radius_km != null
                            ? `${profileData.worker.service_radius_km} km`
                            : "Not specified"}
                        </strong>
                      </div>
                      <div><span>Completed services</span><strong>{profileData.worker?.completed_services ?? 0}</strong></div>
                      <div><span>Free opportunities used</span><strong>{profileData.opportunities?.free_used ?? 0}</strong></div>
                      <div><span>Free opportunities remaining</span><strong>{profileData.opportunities?.free_remaining ?? 0}</strong></div>
                    </>
                  )}
                </div>

                <h3>Service history ({profileJobs?.total ?? 0})</h3>
                {profileJobs?.by_status && (
                  <div className="admin-status-summary">
                    {Object.entries(profileJobs.by_status).map(([status, count]) => (
                      <span key={status}>{statusLabel(status)}: {count}</span>
                    ))}
                  </div>
                )}

                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Service</th>
                        <th>Status</th>
                        <th>{adminProfile.kind === "worker" ? "Customer" : "Assigned worker"}</th>
                        <th>Cost</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(profileJobs?.items || []).map((job) => {
                        const cost = job.total_cost ?? job.service_cost ?? job.cost ?? job.price;
                        return (
                          <tr key={job.id}>
                            <td>{job.service || job.profession || "—"}</td>
                            <td>{statusLabel(job.status)}</td>
                            <td>
                              {(() => {
                                const person =
                                  adminProfile.kind === "worker"
                                    ? job.customer
                                    : job.assigned_worker;

                                const fallbackId =
                                  adminProfile.kind === "worker"
                                    ? job.customer_id
                                    : job.assigned_worker_id;

                                return (
                                  <div className="admin-history-person">
                                    <strong>{person?.name || fallbackId || "Not assigned"}</strong>
                                    {person?.phone && <span>{person.phone}</span>}
                                    {person?.email && <span>{person.email}</span>}
                                  </div>
                                );
                              })()}
                            </td>
                            <td>
                              {cost === undefined || cost === null || cost === ""
                                ? "Not recorded"
                                : `₹${Number(cost).toLocaleString("en-IN")}`}
                            </td>
                            <td>{displayDate(job.created_at)}</td>
                          </tr>
                        );
                      })}
                      {!(profileJobs?.items || []).length && (
                        <tr><td colSpan="5">No service history found.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {adminProfile.kind === "worker" && (
                  <>
                    <h3>Subscription history</h3>
                    <div className="admin-table-wrap">
                      <table className="admin-table">
                        <thead>
                          <tr><th>Plan</th><th>Status</th><th>Starts</th><th>Expires</th></tr>
                        </thead>
                        <tbody>
                          {(profileData.subscriptions || []).map((item) => (
                            <tr key={item.id}>
                              <td>{item.plan || "—"}</td>
                              <td>{statusLabel(item.status)}</td>
                              <td>{displayDate(item.starts_at)}</td>
                              <td>{displayDate(item.expires_at)}</td>
                            </tr>
                          ))}
                          {!(profileData.subscriptions || []).length && (
                            <tr><td colSpan="4">No subscriptions found.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </section>
            )}

            </details>

            <details className="admin-collapsible">
              <summary id="admin-workers-section" className="admin-section-anchor">Worker directory</summary>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Profession</th>
                    <th>Skills</th>
                    <th>Experience</th>
                    <th>Availability</th>
                    <th>Rating</th>
                    <th>Verified</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {adminWorkers.map((item) => (
                    <tr key={item.id}>
                      <td>{item.profession || "—"}</td>
                      <td>{Array.isArray(item.skills) ? item.skills.join(", ") : item.skills || "—"}</td>
                      <td>{item.experience_years ?? "—"}</td>
                      <td>{statusLabel(item.availability)}</td>
                      <td>{Number(item.rating || 0).toFixed(1)}</td>
                      <td>{item.is_verified ? "Yes" : "No"}</td>
                      <td>
                        <button
                          className="btn btn-outline admin-small-button"
                          onClick={() => loadAdminProfile("worker", item.id)}
                        >
                          View details
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!adminWorkers.length && (
                    <tr><td colSpan="7">No workers returned.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            </details>

            <details className="admin-collapsible">
              <summary>Request filters</summary>
            <div className="admin-filter-grid">
              <label>
                Status
                <select
                  value={adminRequestFilters.status}
                  onChange={(e) => setAdminRequestFilters((old) => ({ ...old, status: e.target.value }))}
                >
                  <option value="">All statuses</option>
                  {["requested", "accepted", "confirmed", "on_the_way", "arrived", "in_progress", "completed", "rejected", "cancelled", "expired"].map((status) => (
                    <option key={status} value={status}>{statusLabel(status)}</option>
                  ))}
                </select>
              </label>
              <label>
                Customer
                <select
                  value={adminRequestFilters.customer_id}
                  onChange={(e) => setAdminRequestFilters((old) => ({ ...old, customer_id: e.target.value }))}
                >
                  <option value="">All customers</option>
                  {adminUsers.filter((item) => item.role === "customer").map((item) => (
                    <option key={item.id} value={item.id}>{item.name || item.email || item.id}</option>
                  ))}
                </select>
              </label>
              <label>
                Worker
                <select
                  value={adminRequestFilters.worker_id}
                  onChange={(e) => setAdminRequestFilters((old) => ({ ...old, worker_id: e.target.value }))}
                >
                  <option value="">All workers</option>
                  {adminWorkers.map((item) => (
                    <option key={item.id} value={item.user_id}>{item.profession || item.user_id}</option>
                  ))}
                </select>
              </label>
              <label>
                Profession
                <input
                  value={adminRequestFilters.profession}
                  onChange={(e) => setAdminRequestFilters((old) => ({ ...old, profession: e.target.value }))}
                  placeholder="e.g. Plumber"
                  maxLength={100}
                />
              </label>
              <label>
                From date
                <input
                  type="date"
                  value={adminRequestFilters.start_date}
                  onChange={(e) => setAdminRequestFilters((old) => ({ ...old, start_date: e.target.value }))}
                />
              </label>
              <label>
                To date
                <input
                  type="date"
                  value={adminRequestFilters.end_date}
                  onChange={(e) => setAdminRequestFilters((old) => ({ ...old, end_date: e.target.value }))}
                />
              </label>
            </div>
            <div className="admin-filter-actions">
              <button className="btn btn-primary" onClick={applyFilters} disabled={adminLoading}>
                Apply filters
              </button>
              <button className="btn btn-outline" onClick={clearFilters} disabled={adminLoading}>
                Clear filters
              </button>
            </div>

            </details>

            <details className="admin-collapsible">
              <summary id="admin-requests-section" className="admin-section-anchor">Service requests ({adminRequests.length})</summary>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Customer</th>
                    <th>Assigned worker</th>
                    <th>Status</th>
                    <th>Created (IST)</th>
                  </tr>
                </thead>
                <tbody>
                  {adminRequests.map((item) => (
                    <tr key={item.id}>
                      <td>{item.service || "—"}</td>
                      <td>
                        <div className="admin-history-person">
                          <strong>{item.customer?.name || item.customer_id || "—"}</strong>
                          {item.customer?.phone && (
                            <span>
                              <a href={`tel:${item.customer.phone}`}>{item.customer.phone}</a>
                            </span>
                          )}
                          {item.customer?.email && <span>{item.customer.email}</span>}
                        </div>
                      </td>
                      <td>
                        <div className="admin-history-person">
                          <strong>
                            {item.assigned_worker?.name || item.assigned_worker_id || "Not assigned"}
                          </strong>
                          {item.assigned_worker?.profession && (
                            <span>{item.assigned_worker.profession}</span>
                          )}
                          {item.assigned_worker?.phone && (
                            <span>
                              <a href={`tel:${item.assigned_worker.phone}`}>
                                {item.assigned_worker.phone}
                              </a>
                            </span>
                          )}
                          {item.assigned_worker?.email && (
                            <span>{item.assigned_worker.email}</span>
                          )}
                        </div>
                      </td>
                      <td>{statusLabel(item.status)}</td>
                      <td>{displayDate(item.created_at)}</td>
                    </tr>
                  ))}
                  {!adminRequests.length && (
                    <tr><td colSpan="5">No requests match these filters.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            </details>

            <details className="admin-collapsible">
              <summary id="admin-subscriptions-section" className="admin-section-anchor">Subscription records ({adminSubscriptions.length})</summary>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr><th>Worker ID</th><th>Plan</th><th>Status</th><th>Starts</th><th>Expires</th><th>Payment ID</th></tr>
                </thead>
                <tbody>
                  {adminSubscriptions.map((item) => (
                    <tr key={item.id}>
                      <td>{item.worker_id || "—"}</td>
                      <td>{item.plan || "—"}</td>
                      <td>{statusLabel(item.status)}</td>
                      <td>{displayDate(item.starts_at)}</td>
                      <td>{displayDate(item.expires_at)}</td>
                      <td>{item.payment_id || "—"}</td>
                    </tr>
                  ))}
                  {!adminSubscriptions.length && (
                    <tr><td colSpan="6">No subscriptions returned.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            </details>

            <details className="admin-collapsible">
              <summary id="admin-payments-section" className="admin-section-anchor">Payment records ({adminPayments.length})</summary>
            <p>Payment status is displayed from backend records; this dashboard does not manually verify payments.</p>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr><th>Worker ID</th><th>Plan</th><th>Amount</th><th>Currency</th><th>Status</th><th>Razorpay payment ID</th></tr>
                </thead>
                <tbody>
                  {adminPayments.map((item) => (
                    <tr key={item.id}>
                      <td>{item.worker_id || "—"}</td>
                      <td>{item.plan || "—"}</td>
                      <td>{item.currency === "INR" ? displayAmount(item.amount) : `${item.amount ?? "—"} ${item.currency || ""}`}</td>
                      <td>{item.currency || "—"}</td>
                      <td>{statusLabel(item.status)}</td>
                      <td>{item.razorpay_payment_id || "—"}</td>
                    </tr>
                  ))}
                  {!adminPayments.length && (
                    <tr><td colSpan="6">No payment records returned.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </details>

          <details className="admin-collapsible admin-aadhaar-collapsible">
            <summary>Aadhaar verification queue</summary>
            <section className="admin-aadhaar-section">
            <div className="section-heading">
              <div>
                <span className="eyebrow">PRIVATE IDENTITY REVIEW</span>

                <p>Only authenticated administrators can preview documents or decide verification.</p>
              </div>
              <button
                className="btn btn-outline"
                type="button"
                onClick={() => loadAdminAadhaar()}
                disabled={adminAadhaarLoading}
              >
                {adminAadhaarLoading ? "Loading…" : "Refresh queue"}
              </button>
            </div>

            {adminAadhaarError && (
              <div className="notice notice-error" role="alert">{adminAadhaarError}</div>
            )}

            <label className="aadhaar-filter-label">
              Filter documents
              <select
                value={adminAadhaarFilter}
                onChange={(event) => {
                  const nextStatus = event.target.value;
                  setAdminAadhaarFilter(nextStatus);
                  loadAdminAadhaar(nextStatus);
                }}
              >
                <option value="pending">Pending review</option>
                <option value="verified">Verified</option>
                <option value="rejected">Rejected</option>
                <option value="all">All documents</option>
              </select>
            </label>

            {adminAadhaarLoading && <p>Loading verification records…</p>}
            {!adminAadhaarLoading && adminAadhaarItems.length === 0 && (
              <div className="empty-state">
                <span>🪪</span>
                <h3>No documents found</h3>
                <p>No Aadhaar records match this filter.</p>
              </div>
            )}

            <div className="aadhaar-admin-list">
              {adminAadhaarItems.map((item) => (
                <article className="aadhaar-admin-card" key={item.worker_id}>
                  <div className="aadhaar-admin-card-header">
                    <div>
                      <h3>{item.worker?.name || "Worker"}</h3>
                      <p>{item.worker?.email || "No email"}{item.worker?.phone ? ` · ${item.worker.phone}` : ""}</p>
                    </div>
                    <span className={`aadhaar-status aadhaar-status-${item.status}`}>
                      {item.status}
                    </span>
                  </div>
                  <dl className="aadhaar-metadata">
                    <div><dt>Worker ID</dt><dd>{item.worker_id}</dd></div>
                    <div><dt>Filename</dt><dd>{item.filename || "Document"}</dd></div>
                    <div><dt>Uploaded</dt><dd>{displayDate(item.uploaded_at)}</dd></div>
                    <div><dt>Reviewed</dt><dd>{displayDate(item.reviewed_at)}</dd></div>
                  </dl>

                  {item.rejection_reason && (
                    <p className="notice notice-error">
                      <strong>Rejection reason:</strong> {item.rejection_reason}
                    </p>
                  )}

                  <div className="aadhaar-admin-actions">
                    <button
                      className="btn btn-outline"
                      type="button"
                      onClick={() => previewAdminAadhaar(item)}
                    >
                      Preview document
                    </button>
                    {item.status !== "verified" && (
                      <button
                        className="btn btn-primary"
                        type="button"
                        disabled={Boolean(aadhaarDecisionLoading[item.worker_id])}
                        onClick={() => decideAdminAadhaar(item, "verified")}
                      >
                        {aadhaarDecisionLoading[item.worker_id] ? "Saving…" : "Verify"}
                      </button>
                    )}
                    {item.status !== "rejected" && (
                      <div className="aadhaar-reject-control">
                        <input
                          aria-label={`Rejection reason for ${item.worker?.name || item.worker_id}`}
                          value={aadhaarRejectionReasons[item.worker_id] || ""}
                          onChange={(event) =>
                            setAadhaarRejectionReasons((old) => ({
                              ...old,
                              [item.worker_id]: event.target.value,
                            }))
                          }
                          placeholder="Reason required to reject"
                          maxLength={1000}
                        />
                        <button
                          className="btn btn-outline"
                          type="button"
                          disabled={Boolean(aadhaarDecisionLoading[item.worker_id])}
                          onClick={() => decideAdminAadhaar(item, "rejected")}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>

          </details>

          <section className="admin-recent-activity">
            <div className="section-heading">
              <div>
                <span className="eyebrow">LIVE MARKETPLACE SNAPSHOT</span>
                <h2>Currently Running / Recent Activity</h2>
                <p>Latest 10 service requests, including active and completed work.</p>
              </div>
              <button
                type="button"
                className="btn btn-outline"
                onClick={loadAdminData}
                disabled={adminLoading}
              >
                {adminLoading ? "Refreshing..." : "Refresh activity"}
              </button>
            </div>

            {(() => {
              const recentItems = [...adminRecentRequests]
                .sort((a, b) => {
                  const dateA = new Date(a.updated_at || a.created_at || 0).getTime();
                  const dateB = new Date(b.updated_at || b.created_at || 0).getTime();
                  return dateB - dateA;
                })
                .slice(0, 10);

              const activeStatuses = new Set([
                "requested", "accepted", "confirmed",
                "on_the_way", "arrived", "in_progress",
              ]);

              return (
                <>
                  <div className="admin-activity-summary">
                    <span>Showing <strong>{recentItems.length}</strong> of the latest requests</span>
                    <span>
                      Active in this list: <strong>
                        {recentItems.filter((item) => activeStatuses.has(item.status)).length}
                      </strong>
                    </span>
                  </div>

                  <div className="admin-table-wrap">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Service</th>
                          <th>Customer</th>
                          <th>Assigned worker</th>
                          <th>Status</th>
                          <th>Last activity (IST)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentItems.map((item) => (
                          <tr key={item.id}>
                            <td>{item.service || "—"}</td>
                            <td>{item.customer?.name || item.customer_id || "—"}</td>
                            <td>{item.assigned_worker?.name || item.assigned_worker_id || "Not assigned"}</td>
                            <td>
                              <span className={
                                "admin-activity-status " +
                                (activeStatuses.has(item.status)
                                  ? "is-active"
                                  : item.status === "completed"
                                    ? "is-completed"
                                    : "is-other")
                              }>
                                {statusLabel(item.status)}
                              </span>
                            </td>
                            <td>{displayDate(item.updated_at || item.created_at)}</td>
                          </tr>
                        ))}
                        {!recentItems.length && (
                          <tr><td colSpan="5">No recent service requests found.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              );
            })()}
          </section>


          </>
        )}
      </section>

      {aadhaarPreview && (
        <div
          className="aadhaar-preview-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) closeAadhaarPreview();
          }}
        >
          <section
            className="aadhaar-preview-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Private Aadhaar document preview"
          >
            <div className="aadhaar-preview-header">
              <h2>{aadhaarPreview.filename}</h2>
              <button className="btn btn-outline" type="button" onClick={closeAadhaarPreview}>
                Close preview
              </button>
            </div>
            {aadhaarPreview.contentType?.startsWith("image/") ? (
              <img src={aadhaarPreview.url} alt="Private Aadhaar document preview" />
            ) : (
              <iframe title="Private Aadhaar PDF preview" src={aadhaarPreview.url} />
            )}
          </section>
        </div>
      )}
      </>
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

      {/* SOLVIX_PRO_DASHBOARD_PHONE_V1 */}
      <section className="dashboard-overview">
        <div className="dashboard-overview-heading">
          <div>
            <span className="eyebrow">YOUR ACTIVITY</span>
            <h2>{user?.role === "worker" ? "Professional overview" : "Booking overview"}</h2>
            <p>
              {user?.role === "worker"
                ? "Track jobs assigned directly to your account."
                : "Keep track of your service bookings and progress."}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              const endpoint =
                user?.role === "worker"
                  ? "/api/requests/worker/stats"
                  : "/api/requests/customer/stats";

              setDashboardStatsLoading(true);
              api.get(endpoint)
                .then((response) => setDashboardStats(response.data))
                .catch((err) => flashError(getError(err)))
                .finally(() => setDashboardStatsLoading(false));
            }}
            disabled={dashboardStatsLoading}
          >
            {dashboardStatsLoading ? "Refreshing..." : "↻ Refresh stats"}
          </button>
        </div>

        {dashboardStatsLoading && !dashboardStats && (
          <p className="helper-text" role="status">Loading your activity...</p>
        )}

        <div className="dashboard-metrics">
          <article className="dashboard-metric">
            <span>{user?.role === "worker" ? "Total assigned jobs" : "Total bookings"}</span>
            <strong>
              {dashboardStats
                ? dashboardStats.total_jobs ?? dashboardStats.total_bookings ?? 0
                : "—"}
            </strong>
            <small>All your recorded requests</small>
          </article>

          <article className="dashboard-metric">
            <span>{user?.role === "worker" ? "Active jobs" : "Active bookings"}</span>
            <strong>
              {dashboardStats
                ? dashboardStats.active_jobs ?? dashboardStats.active_bookings ?? 0
                : "—"}
            </strong>
            <small>Currently in progress</small>
          </article>

          <article className="dashboard-metric">
            <span>{user?.role === "worker" ? "Completed jobs" : "Completed bookings"}</span>
            <strong>
              {dashboardStats
                ? dashboardStats.completed_jobs ?? dashboardStats.completed_bookings ?? 0
                : "—"}
            </strong>
            <small>Successfully completed</small>
          </article>

          <article className="dashboard-metric dashboard-metric-highlight">
            <span>Completion rate</span>
            <strong>{dashboardStats ? `${dashboardStats.completion_rate ?? 0}%` : "—"}</strong>
            <small>Completed jobs ÷ completed and cancelled jobs</small>
          </article>
        </div>

        {dashboardStats && (
          <div className="dashboard-recent">
            <div className="dashboard-recent-heading">
              <h3>Recent activity</h3>
              <span>{(dashboardStats.recent_requests || []).length} recent records</span>
            </div>

            {(dashboardStats.recent_requests || []).length ? (
              <div className="dashboard-recent-list">
                {dashboardStats.recent_requests.map((item) => (
                  <article className="dashboard-recent-item" key={item.id}>
                    <div className="dashboard-recent-icon" aria-hidden="true">✓</div>
                    <div className="dashboard-recent-copy">
                      <strong>{item.service || "Service request"}</strong>
                      <span>
                        {item.created_at ? formatIST(item.created_at) : "Date unavailable"}
                      </span>
                    </div>
                    <span className={`dashboard-status status-${String(item.status || "requested").toLowerCase()}`}>
                      {statusLabel(item.status)}
                    </span>
                  </article>
                ))}
              </div>
            ) : (
              <p className="helper-text">
                No bookings recorded yet. Your activity will appear here.
              </p>
            )}
          </div>
        )}
      </section>

      <section className="dashboard-phone-panel">
        <div>
          <span className="eyebrow">ACCOUNT CONTACT</span>
          <h3>Keep your phone number up to date</h3>
          <p>
            A valid phone number is required before creating a booking or accepting a job.
          </p>
        </div>
        <form className="dashboard-phone-form" onSubmit={saveAccountPhone}>
          <label htmlFor="dashboard-phone">Phone number</label>
          <input
            id="dashboard-phone"
            type="tel"
            inputMode="numeric"
            autoComplete="tel"
            minLength={10}
            maxLength={10}
            pattern="[0-9]{10}"
            value={phoneInput}
            onChange={(event) => setPhoneInput(event.target.value)}
            placeholder="Enter 10-digit mobile number"
            required
          />
          <button className="btn btn-primary" type="submit" disabled={phoneSaving}>
            {phoneSaving ? "Saving..." : "Save phone number"}
          </button>
        </form>
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

          {/* SOLVIX_WORKER_FEEDBACK_PANEL_V1 */}
          <section className="section-block">
            <div className="panel">
              <span className="eyebrow">CUSTOMER REVIEWS</span>
              <h2>Your ratings &amp; feedback</h2>
              <p>
                See how customers rate your completed services and what they
                say about their experience.
              </p>

              <div className="subscription-summary">
                <div className="subscription-stat">
                  <span>Average rating</span>
                  <strong>
                    {workerReviews.length
                      ? (
                          workerReviews.reduce(
                            (total, review) =>
                              total + Number(review.rating || 0),
                            0
                          ) / workerReviews.length
                        ).toFixed(1)
                      : "—"}
                    {" "}★
                  </strong>
                </div>

                <div className="subscription-stat">
                  <span>Total reviews</span>
                  <strong>{workerReviews.length}</strong>
                </div>
              </div>

              {workerReviewsLoading ? (
                <p role="status">Loading customer feedback...</p>
              ) : workerReviews.length === 0 ? (
                <p className="helper-text">
                  No customer reviews yet. Once customers review your completed
                  services, their feedback will appear here.
                </p>
              ) : (
                <div className="worker-review-list">
                  {workerReviews.map((review) => (
                    <article className="worker-review-item" key={review.id}>
                      <div className="worker-review-rating">
                        {"★".repeat(
                          Math.max(
                            0,
                            Math.min(5, Number(review.rating) || 0)
                          )
                        )}
                        {"☆".repeat(
                          5 -
                            Math.max(
                              0,
                              Math.min(5, Number(review.rating) || 0)
                            )
                        )}
                        {" "}
                        <span>{Number(review.rating || 0)}/5</span>
                      </div>

                      <strong>{review.service || "Completed service"}</strong>

                      {review.feedback ? (
                        <p>{review.feedback}</p>
                      ) : (
                        <p className="helper-text">
                          Customer left a star rating without written feedback.
                        </p>
                      )}

                      {review.created_at && (
                        <small className="muted">
                          {formatIST(review.created_at)}
                        </small>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>

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
          <span className="eyebrow">
            {authStep === "login-otp"
              ? "VERIFY YOUR EMAIL"
              : authStep === "forgot"
                ? "ACCOUNT RECOVERY"
                : authStep === "reset"
                  ? "RESET PASSWORD"
                  : authMode === "login"
                    ? "WELCOME BACK"
                    : "GET STARTED"}
          </span>
          <h2>
            {authStep === "login-otp"
              ? "Enter login OTP"
              : authStep === "forgot"
                ? "Forgot password?"
                : authStep === "reset"
                  ? "Choose a new password"
                  : authMode === "login"
                    ? "Log in to SOLVIX"
                    : "Create your account"}
          </h2>
          <p>
            {authStep === "login-otp"
              ? `Enter the 6-digit code sent to ${authForm.email}.`
              : authStep === "forgot"
                ? "Enter your registered email to request a reset code."
                : authStep === "reset"
                  ? "Enter the reset code and your new password."
                  : authMode === "login"
                    ? "Enter your details to continue."
                    : "Join your local service community."}
          </p>
        </div>

        {authStep === "credentials" && (
          <div className="auth-switch">
            <button type="button" className={authForm.role === "customer" ? "active" : ""} onClick={() => setAuthForm((old) => ({ ...old, role: "customer" }))}>I'm a customer</button>
            <button type="button" className={authForm.role === "worker" ? "active" : ""} onClick={() => setAuthForm((old) => ({ ...old, role: "worker" }))}>I'm a professional</button>
          </div>
        )}

        <form className="auth-form" onSubmit={handleAuth}>
          {authStep === "credentials" && authMode === "register" && (
            <label>Full name<input name="name" required minLength="2" maxLength="100" autoComplete="name" value={authForm.name} onChange={updateAuthField} placeholder="Your full name" /></label>
          )}

          <label>
            Email address
            <input
              type="email"
              name="email"
              required
              autoComplete="email"
              readOnly={authStep === "login-otp" || authStep === "reset"}
              value={authForm.email}
              onChange={updateAuthField}
              placeholder="you@example.com"
            />
          </label>

          {authStep === "credentials" && authMode === "register" && (
            <label>Phone number<input type="tel" name="phone" required minLength={10} maxLength={10} pattern="[0-9]{10}" inputMode="numeric" autoComplete="tel" value={authForm.phone} onChange={updateAuthField} placeholder="Enter 10-digit mobile number" /></label>
          )}

          {authStep === "credentials" &&
            authMode === "register" &&
            authForm.role === "worker" && (
              <label>
                Choose your profession
                <select
                  required
                  value={workerProfile.profession}
                  onChange={(event) => {
                    const profession = event.target.value;
                    setWorkerProfile((old) => ({ ...old, profession }));
                    localStorage.setItem(
                      "solvix_pending_profession",
                      profession
                    );
                  }}
                >
                  {SERVICES.filter((service) => service.name !== "Other").map(
                    (service) => (
                      <option key={service.name} value={service.name}>
                        {service.icon} {service.name}
                      </option>
                    )
                  )}
                  <option value="Other">✨ Other</option>
                </select>
                <span className="optional">
                  You can complete your skills and service location after signing in.
                </span>
              </label>
            )}

          {authStep === "credentials" && authMode !== "register" && (
            <label>Password<input type="password" name="password" required minLength="8" maxLength="128" autoComplete="current-password" value={authForm.password} onChange={updateAuthField} placeholder="Your password" /></label>
          )}

          {authStep === "credentials" && authMode === "register" && (
            <label>Password<input type="password" name="password" required minLength="8" maxLength="128" autoComplete="new-password" value={authForm.password} onChange={updateAuthField} placeholder="At least 8 characters" /></label>
          )}

          {(authStep === "login-otp" || authStep === "reset") && (
            <label>
              {authStep === "login-otp" ? "Login verification code" : "Password-reset code"}
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                required
                value={authOtp}
                onChange={(event) => setAuthOtp(event.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="Enter 6-digit OTP"
              />
            </label>
          )}

          {authStep === "reset" && (
            <label>
              New password
              <input
                type="password"
                name="password"
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                value={authForm.password}
                onChange={updateAuthField}
                placeholder="At least 8 characters"
              />
            </label>
          )}

          {authStep === "forgot" && (
            <p className="auth-terms">We'll show the same confirmation whether or not the email belongs to an account.</p>
          )}

          <button className="btn btn-primary full-width auth-submit" type="submit" disabled={loading}>
            {loading
              ? "Please wait..."
              : authStep === "login-otp"
                ? "Verify and log in →"
                : authStep === "forgot"
                  ? "Send reset code →"
                  : authStep === "reset"
                    ? "Reset password →"
                    : authMode === "login"
                      ? "Log in →"
                      : "Create account →"}
          </button>
        </form>

        {authStep === "credentials" && authMode === "login" && (
          <p className="auth-alternate">
            <button type="button" onClick={() => { clearMessages(); setAuthStep("forgot"); setAuthOtp(""); }}>
              Forgot password?
            </button>
          </p>
        )}

        {authStep === "credentials" && import.meta.env.VITE_GOOGLE_CLIENT_ID && (
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
          {authStep !== "credentials" ? "Changed your mind?" : authMode === "login" ? "New to SOLVIX?" : "Already have an account?"}
          <button
            type="button"
            onClick={() => {
              clearMessages();
              setAuthOtp("");
              setAuthStep("credentials");
              setAuthMode((old) =>
                authStep !== "credentials"
                  ? "login"
                  : old === "login"
                    ? "register"
                    : "login"
              );
              setAuthForm((old) => ({ ...old, password: "" }));
            }}
          >
            {authStep !== "credentials" ? "Back to login" : authMode === "login" ? "Create an account" : "Log in"}
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

        <div className="worker-location-block">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">SERVICE LOCATION</span>
              <h3>Where can you provide services?</h3>
              <p>Detect your current location or enter coordinates manually.</p>
            </div>
            <span className="location-icon">📍</span>
          </div>

          <button
            className="btn btn-outline geo-button"
            type="button"
            onClick={getCoordinates}
          >
            ◎ Detect my location
          </button>

          {locationMessage && (
            <p className="helper-text" role="status">{locationMessage}</p>
          )}

          <div className="form-grid two-columns">
            <label>
              Latitude
              <input
                type="number"
                step="any"
                min="-90"
                max="90"
                placeholder="e.g. 28.6139"
                value={coords.latitude}
                onChange={(event) =>
                  setCoords((old) => ({
                    ...old,
                    latitude: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Longitude
              <input
                type="number"
                step="any"
                min="-180"
                max="180"
                placeholder="e.g. 77.2090"
                value={coords.longitude}
                onChange={(event) =>
                  setCoords((old) => ({
                    ...old,
                    longitude: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <p className="helper-text">
            Your location helps customers find professionals in their service area.
          </p>
        </div>

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

      <section className="panel aadhaar-panel" aria-labelledby="worker-aadhaar-heading">
        <span className="eyebrow">IDENTITY VERIFICATION</span>
        <h2 id="worker-aadhaar-heading">Aadhaar verification</h2>
        <p>
          Upload a PDF or image for private admin review. Aadhaar is not required
          for your first five free job opportunities. After the free quota,
          paid job access requires both an active subscription and verified Aadhaar.
        </p>

        <div className="aadhaar-status-row">
          <span>Verification status</span>
          <strong className={`aadhaar-status aadhaar-status-${aadhaarStatus?.status || "unknown"}`}>
            {aadhaarStatusLoading
              ? "Loading…"
              : ({
                  not_uploaded: "Not Uploaded",
                  pending: "Pending",
                  verified: "Verified",
                  rejected: "Rejected",
                }[aadhaarStatus?.status] || "Unknown")}
          </strong>
        </div>

        {aadhaarStatus?.uploaded_at && (
          <p className="helper-text">
            Last uploaded: {displayDate(aadhaarStatus.uploaded_at)}
          </p>
        )}
        {aadhaarStatus?.reviewed_at && (
          <p className="helper-text">
            Reviewed: {displayDate(aadhaarStatus.reviewed_at)}
          </p>
        )}
        {aadhaarStatus?.status === "rejected" && aadhaarStatus?.rejection_reason && (
          <div className="notice notice-error" role="alert">
            <strong>Reason for rejection:</strong> {aadhaarStatus.rejection_reason}
            <p>You can submit a corrected document below.</p>
          </div>
        )}

        {aadhaarUploadError && (
          <div className="notice notice-error" role="alert">{aadhaarUploadError}</div>
        )}
        {aadhaarUploadMessage && (
          <div className="notice notice-success" role="status">{aadhaarUploadMessage}</div>
        )}

        <form className="aadhaar-upload-form" onSubmit={uploadWorkerAadhaar}>
          <label htmlFor="worker-aadhaar-file">
            Aadhaar document (PDF, JPEG, PNG, or WebP; maximum 10 MB)
          </label>
          <input
            id="worker-aadhaar-file"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
            onChange={(event) => {
              setAadhaarFile(event.target.files?.[0] || null);
              setAadhaarUploadError("");
              setAadhaarUploadMessage("");
            }}
            disabled={aadhaarUploadLoading}
          />
          <button
            className="btn btn-primary"
            type="submit"
            disabled={aadhaarUploadLoading}
          >
            {aadhaarUploadLoading ? "Uploading…" : aadhaarStatus?.status === "rejected"
              ? "Resubmit document →"
              : "Upload for verification →"}
          </button>
        </form>
        <p className="helper-text">
          Documents are submitted to the protected verification service and are not
          displayed publicly on your profile.
        </p>
      </section>
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

            <section className="home-stats" aria-label="SOLVIX marketplace statistics">
              <div>
                <strong>{publicStats ? Number(publicStats.users?.customers || 0).toLocaleString() : "—"}</strong>
                <span>Customers</span>
              </div>
              <div>
                <strong>{publicStats ? Number(publicStats.workers?.total || 0).toLocaleString() : "—"}</strong>
                <span>Registered professionals</span>
              </div>
              <div>
                <strong>{publicStats ? Number(publicStats.workers?.available || 0).toLocaleString() : "—"}</strong>
                <span>Available professionals</span>
              </div>
              <div>
                <strong>{publicStats ? Number(publicStats.requests?.completed || 0).toLocaleString() : "—"}</strong>
                <span>Completed services</span>
              </div>
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
        {page === "admin" && user?.role === "admin" && AdminPage()}
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
        <div className="footer-main">
          <div className="footer-brand">
            <span className="brand-mark">S</span>
            <span>
              SOLVIX
              <small>Connect. Solve. Get It Done.</small>
            </span>
          </div>

          <p className="footer-description">
            Bringing local people and practical solutions closer together.
          </p>

          <section className="footer-developer" aria-label="Developer contact information">
            <span className="footer-eyebrow">THE PEOPLE BEHIND SOLVIX</span>
            <h3>Developed &amp; Managed By</h3>
            <p className="footer-developer-name">PRABHAKAR SINGH KSHATRIYA</p>

            <div className="footer-contact">
              <a href="mailto:prabhakarsingh5668@gmail.com">
                <span aria-hidden="true">✉</span>
                <span>prabhakarsingh5668@gmail.com</span>
              </a>
              <a href="tel:+917565081457">
                <span aria-hidden="true">☎</span>
                <span>+91 75650 81457</span>
              </a>
            </div>
          </section>
        </div>

        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} SOLVIX. All rights reserved.</span>
          <span className={`footer-api ${backendStatus === "online" ? "api-ok" : ""}`}>
            <i /> API {backendStatus}
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
