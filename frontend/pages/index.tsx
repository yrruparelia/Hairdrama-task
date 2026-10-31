import { FormEvent, useEffect, useState } from "react";
import axios from "axios";

type User = {
  id: string;
  sub?: string;
  email: string;
  name: string;
  avatar_url?: string;
};

type Task = {
  id: string;
  title: string;
  description?: string;
  status: "todo" | "in_progress" | "done";
  priority: "low" | "medium" | "high";
  due_date?: string | null;
  assigned_to?: string | null;
  created_by: string;
  created_at?: string;
  assignee?: User | null;
  creator?: User | null;
};

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000",
});

const columns: Array<{ key: Task["status"]; label: string }> = [
  { key: "todo", label: "To do" },
  { key: "in_progress", label: "In progress" },
  { key: "done", label: "Done" },
];

export default function Home() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [darkMode, setDarkMode] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<"self" | "delegated">("self");
  const [savingTaskId, setSavingTaskId] = useState<string | null>(null);
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);
  const [taskToRemove, setTaskToRemove] = useState<Task | null>(null);
  const [creatingTask, setCreatingTask] = useState(false);
  const [sortBy, setSortBy] = useState<
    "priority-asc" | "priority-desc" | "due-asc" | "due-desc" | "created-asc" | "created-desc"
  >("created-desc");
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "medium",
    due_date: "",
    assigned_to: "",
  });

  const currentUserId = user?.id || user?.sub || "";
  const selfTasks = tasks.filter(
    (task) =>
      task.created_by === currentUserId &&
      (!task.assigned_to || task.assigned_to === currentUserId),
  );
  const delegatedTasks = tasks.filter(
    (task) =>
      task.created_by === currentUserId &&
      task.assigned_to &&
      task.assigned_to !== currentUserId,
  );
  const assignedToMe = tasks.filter(
    (task) =>
      task.assigned_to === currentUserId &&
      task.created_by !== currentUserId,
  );
  const priorityRank: Record<Task["priority"], number> = {
    low: 1,
    medium: 2,
    high: 3,
  };
  const sortTasks = (items: Task[]) =>
    [...items].sort((first, second) => {
      if (sortBy.startsWith("priority")) {
        const difference =
          priorityRank[first.priority] - priorityRank[second.priority];
        return sortBy === "priority-asc" ? difference : -difference;
      }

      if (sortBy.startsWith("due")) {
        const firstDate = first.due_date
          ? new Date(first.due_date).getTime()
          : Number.MAX_SAFE_INTEGER;
        const secondDate = second.due_date
          ? new Date(second.due_date).getTime()
          : Number.MAX_SAFE_INTEGER;
        const difference = firstDate - secondDate;
        return sortBy === "due-asc" ? difference : -difference;
      }

      const firstCreated = first.created_at
        ? new Date(first.created_at).getTime()
        : 0;
      const secondCreated = second.created_at
        ? new Date(second.created_at).getTime()
        : 0;
      const difference = firstCreated - secondCreated;
      return sortBy === "created-asc" ? difference : -difference;
    });

  useEffect(() => {
    setDarkMode(window.localStorage.getItem("hairdrama_theme") === "dark");
    const storedToken = window.localStorage.getItem("hairdrama_token") || "";
    setToken(storedToken);
    if (!storedToken) {
      setLoading(false);
      return;
    }

    void loadData(storedToken);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    window.localStorage.setItem("hairdrama_theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  function toggleTheme() {
    setDarkMode((current) => !current);
  }

  async function loadData(authToken: string) {
    setLoading(true);
    setError("");
    const config = { headers: { Authorization: `Bearer ${authToken}` } };
    try {
      const [meResponse, tasksResponse, usersResponse] = await Promise.all([
        api.get<User>("/auth/me", config),
        api.get<Task[]>("/api/tasks/", config),
        api.get<User[]>("/api/users/", config),
      ]);
      setUser({ ...meResponse.data, id: meResponse.data.id || meResponse.data.sub || "" });
      setTasks(tasksResponse.data);
      setUsers(usersResponse.data);
    } catch (requestError) {
      window.localStorage.removeItem("hairdrama_token");
      setToken("");
      setUser(null);
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  function login() {
    window.location.href = `${api.defaults.baseURL}/auth/google`;
  }

  function logout() {
    window.localStorage.removeItem("hairdrama_token");
    setToken("");
    setUser(null);
    setTasks([]);
    setUsers([]);
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (form.due_date && form.due_date < getToday()) {
      setError("Due date cannot be earlier than today.");
      return;
    }

    const assignedTo =
      formMode === "self" ? currentUserId : form.assigned_to || null;
    const temporaryId = `temporary-${Date.now()}`;
    const selectedAssignee = users.find((item) => item.id === assignedTo);
    const optimisticTask: Task = {
      id: temporaryId,
      title: form.title,
      description: form.description,
      priority: form.priority as Task["priority"],
      due_date: form.due_date || null,
      assigned_to: assignedTo,
      created_by: currentUserId,
      status: "todo",
      creator: user,
      assignee: formMode === "self" ? user : selectedAssignee || null,
    };
    setCreatingTask(true);
    setTasks((current) => [optimisticTask, ...current]);

    try {
      const response = await api.post<Task>(
        "/api/tasks/",
        {
          ...form,
          assigned_to: assignedTo,
          due_date: form.due_date || null,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setTasks((current) =>
        current.map((task) => (task.id === temporaryId ? response.data : task)),
      );
      setForm({
        title: "",
        description: "",
        priority: "medium",
        due_date: "",
        assigned_to: "",
      });
      setShowForm(false);
    } catch (requestError) {
      setTasks((current) =>
        current.filter((task) => task.id !== temporaryId),
      );
      setError(getErrorMessage(requestError));
    } finally {
      setCreatingTask(false);
    }
  }

  async function updateStatus(task: Task, status: Task["status"]) {
    setError("");
    const previousTasks = tasks;
    setSavingTaskId(task.id);
    setTasks((current) =>
      current.map((item) => (item.id === task.id ? { ...item, status } : item)),
    );
    try {
      const response = await api.patch<Task>(
        `/api/tasks/${task.id}`,
        { status },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setTasks((current) =>
        current.map((item) => (item.id === task.id ? response.data : item)),
      );
    } catch (requestError) {
      setTasks(previousTasks);
      setError(getErrorMessage(requestError));
    } finally {
      setSavingTaskId(null);
    }
  }

  async function deleteTask(task: Task) {
    setError("");
    setDeletingTaskId(task.id);
    try {
      await api.delete(`/api/tasks/${task.id}`, {
        headers: { Authorization: "Bearer " + token },
      });
      setTasks((current) => current.filter((item) => item.id !== task.id));
      setTaskToRemove(null);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setDeletingTaskId(null);
    }
  }

  function openTaskForm(mode: "self" | "delegated") {
    setFormMode(mode);
    setForm({ title: "", description: "", priority: "medium", due_date: "", assigned_to: "" });
    setShowForm(true);
  }

  function canUpdateStatus(task: Task) {
    return (
      task.assigned_to === currentUserId ||
      (!task.assigned_to && task.created_by === currentUserId)
    );
  }

  function renderBoard(title: string, boardTasks: Task[]) {
    const board = columns.map((column) => ({
      ...column,
      tasks: sortTasks(boardTasks.filter((task) => task.status === column.key)),
    }));

    return (
      <section className="task-section">
        <div className="section-heading">
          <div>
            <h2>{title}</h2>
            <p className="muted">
              {title === "Assigned to others"
                ? "You assign the work; the task doer controls completion."
                : "Tasks you are responsible for completing."}
            </p>
          </div>
          <span className="section-count">{boardTasks.length} {boardTasks.length === 1 ? "task" : "tasks"}</span>
        </div>
        <div className="board">
          {board.map((column) => (
            <div className="column" key={column.key}>
              <div className="column-heading">
                <div className={`column-dot ${column.key}`} />
                <h3>{column.label}</h3>
                <span className="count">{column.tasks.length}</span>
              </div>
              <div className="task-list">
                {column.tasks.length === 0 && (
                  <div className="empty">
                    <span className="empty-icon">✓</span>
                    <span>No {column.label.toLowerCase()} tasks</span>
                  </div>
                )}
                {column.tasks.map((task) => (
                  <article className="task-card" key={task.id}>
                    <div className="task-card-top">
                      <span className={`priority ${task.priority}`}>{task.priority}</span>
                      {task.due_date && (
                        <time className={getDueState(task) === "overdue" ? "overdue-date" : isDueSoon(task.due_date) ? "due-soon" : ""}>
                          <span aria-hidden="true">◷</span> {formatDate(task.due_date)}
                        </time>
                      )}
                    </div>
                    <h3>{task.title}</h3>
                    {task.description && <p>{task.description}</p>}
                    {getDueState(task) === "overdue" && (
                      <div className="overdue-label">
                        <span aria-hidden="true">!</span>
                        Overdue by {getOverdueDays(task.due_date as string)}{" "}
                        {getOverdueDays(task.due_date as string) === 1 ? "day" : "days"}
                      </div>
                    )}
                    {task.assigned_to && task.assigned_to !== task.created_by && (
                      <div className="task-people">
                        <div className="person">
                          {task.creator?.avatar_url ? (
                            <img className="mini-avatar" src={task.creator.avatar_url} alt="" />
                          ) : (
                            <span className="mini-avatar placeholder">{getInitials(task.creator?.name || "You")}</span>
                          )}
                          <span><b>From</b> {task.creator?.name || task.creator?.email || "You"}</span>
                        </div>
                        <div className="person">
                          {task.assignee?.avatar_url ? (
                            <img className="mini-avatar" src={task.assignee.avatar_url} alt="" />
                          ) : (
                            <span className="mini-avatar placeholder">{task.assignee ? getInitials(task.assignee.name) : "?"}</span>
                          )}
                          <span><b>To</b> {task.assignee?.name || task.assignee?.email || "Unassigned"}</span>
                        </div>
                      </div>
                    )}
                    <div className="task-card-footer">
                      <span className={`status-label ${task.status}`}>
                        <span className="status-dot" />
                        {task.status === "done" ? "Completed" : task.status === "in_progress" ? "In progress" : "Not started"}
                      </span>
                      <div className="task-actions">
                        {canUpdateStatus(task) && task.status !== "done" && (
                          <button
                            className="complete-button"
                            disabled={savingTaskId === task.id}
                            onClick={() =>
                              updateStatus(
                                task,
                                task.status === "todo" ? "in_progress" : "done",
                              )
                            }
                          >
                            {savingTaskId === task.id
                              ? "Saving..."
                              : task.status === "todo"
                                ? "Start"
                                : "Complete"}
                          </button>
                        )}
                        {task.status === "done" && task.created_by === currentUserId && (
                          <button
                            className="delete-button"
                            disabled={deletingTaskId === task.id}
                            onClick={() => setTaskToRemove(task)}
                          >
                            {deletingTaskId === task.id ? "Removing..." : "Remove"}
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (loading) {
    return <main className="centered">Loading your workspace...</main>;
  }

  if (!token || !user) {
    return (
      <main className="login-page">
        <button className="theme-toggle login-theme-toggle" onClick={toggleTheme} aria-label="Toggle color theme">
          <span>{darkMode ? "☀" : "☾"}</span>
          {darkMode ? "Light mode" : "Dark mode"}
        </button>
        <div className="login-shell">
          <section className="login-hero">
            <div className="hero-orb orb-one" />
            <div className="hero-orb orb-two" />
            <p className="eyebrow">A CALMER WAY TO GET WORK DONE</p>
            <h1>Turn busy work into <em>beautiful progress.</em></h1>
            <p className="hero-copy">
              One focused workspace for planning, sharing ownership, and celebrating every finish.
            </p>
            <div className="hero-preview">
              <div className="preview-top"><span className="preview-dot purple" /><span>Today&apos;s focus</span><strong>3 tasks</strong></div>
              <div className="preview-task"><span className="preview-check">✓</span><div><b>Launch the new campaign</b><small>In progress · High priority</small></div><span className="preview-avatar">A</span></div>
              <div className="preview-task faded"><span className="preview-check">✓</span><div><b>Review design feedback</b><small>Assigned to you</small></div><span className="preview-avatar blue">M</span></div>
            </div>
          </section>
          <section className="login-card">
            <div className="login-card-heading">
              <p className="eyebrow">WELCOME BACK</p>
              <h2>Let&apos;s make today count.</h2>
              <p className="muted">Sign in to pick up where you left off.</p>
            </div>
            {error && <p className="error">{error}</p>}
            <button className="google-button" onClick={login}>
              <span className="google-g">G</span>
              Continue with Google
              <span className="button-arrow">→</span>
            </button>
            <p className="small-text">Secure sign-in powered by Google</p>
            <div className="login-perks">
              <span>✦ Clear ownership</span><span>✦ Shared momentum</span>
            </div>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark small">H</div>
          <span>HairDrama Tasks</span>
        </div>
        <div className="account">
          {user.avatar_url ? (
            <img className="avatar" src={user.avatar_url} alt="" />
          ) : (
            <div className="avatar placeholder">{user.name?.[0] || "U"}</div>
          )}
          <div className="account-copy">
            <strong>{user.name || user.email}</strong>
            <span>Workspace member</span>
          </div>
          <button className="text-button" onClick={logout}>
            Log out
          </button>
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle color theme">
            <span>{darkMode ? "☀" : "☾"}</span>
          </button>
        </div>
      </header>

      <section className="content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h1>Task board</h1>
            <p className="muted">A clear view of what needs your attention.</p>
          </div>
          <div className="heading-actions">
            <button className="secondary-button" onClick={() => openTaskForm("self")}>
              + Task for me
            </button>
            <button className="primary-button" onClick={() => openTaskForm("delegated")}>
              + Assign to others
            </button>
          </div>
        </div>

        {error && <p className="error banner">{error}</p>}

        <div className="overview">
          <div className="overview-card">
            <span className="overview-icon purple">◫</span>
            <div><strong>{tasks.length}</strong><span>Total tasks</span></div>
          </div>
          <div className="overview-card">
            <span className="overview-icon amber">◌</span>
            <div><strong>{tasks.filter((task) => task.status !== "done").length}</strong><span>Open tasks</span></div>
          </div>
          <div className="overview-card">
            <span className="overview-icon green">✓</span>
            <div><strong>{tasks.filter((task) => task.status === "done").length}</strong><span>Completed</span></div>
          </div>
          <div className="overview-card">
            <span className="overview-icon blue">↗</span>
            <div><strong>{assignedToMe.length}</strong><span>Assigned to you</span></div>
          </div>
        </div>

        <div className="sort-toolbar">
          <span className="sort-label">View options</span>
          <label htmlFor="task-sort">Sort by</label>
          <select
            id="task-sort"
            value={sortBy}
            onChange={(event) =>
              setSortBy(
                event.target.value as
                  | "priority-asc"
                  | "priority-desc"
                  | "due-asc"
                  | "due-desc"
                  | "created-asc"
                  | "created-desc",
              )
            }
          >
            <option value="created-desc">Newest created</option>
            <option value="created-asc">Oldest created</option>
            <option value="priority-asc">Priority: low to high</option>
            <option value="priority-desc">Priority: high to low</option>
            <option value="due-asc">Due date: earliest first</option>
            <option value="due-desc">Due date: latest first</option>
          </select>
        </div>

        {showForm && (
          <form className="task-form" onSubmit={createTask}>
            <div className="form-heading">
              <h2>{formMode === "self" ? "Create a task for myself" : "Assign a task to someone"}</h2>
              <button
                type="button"
                className="text-button"
                onClick={() => setShowForm(false)}
              >
                Close
              </button>
            </div>
            <label>
              Title
              <input
                required
                value={form.title}
                onChange={(event) =>
                  setForm({ ...form, title: event.target.value })
                }
                placeholder="What needs to be done?"
              />
            </label>
            <label>
              Description
              <textarea
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
                placeholder="Add helpful context"
                rows={3}
              />
            </label>
            <div className="form-grid">
              <label>
                Priority
                <select
                  value={form.priority}
                  onChange={(event) =>
                    setForm({ ...form, priority: event.target.value })
                  }
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label>
                Due date
                <input
                  type="date"
                  value={form.due_date}
                  min={getToday()}
                  onChange={(event) =>
                    setForm({ ...form, due_date: event.target.value })
                  }
                />
              </label>
              {formMode === "delegated" && (
                <label>
                  Task doer
                  <select
                    required
                    value={form.assigned_to}
                    onChange={(event) =>
                      setForm({ ...form, assigned_to: event.target.value })
                    }
                  >
                    <option value="">Choose a user</option>
                    {users
                      .filter((item) => item.id !== currentUserId)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name || item.email}
                        </option>
                      ))}
                  </select>
                </label>
              )}
            </div>
            <button className="primary-button" type="submit" disabled={creatingTask}>
              {creatingTask ? "Creating..." : "Create task"}
            </button>
          </form>
        )}

        {renderBoard("My tasks", selfTasks)}
        {renderBoard("Assigned to others", delegatedTasks)}
        {assignedToMe.length > 0 && renderBoard("Assigned to me", assignedToMe)}
      </section>
      {taskToRemove && (
        <div className="modal-backdrop" role="presentation">
          <section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="remove-task-title">
            <div className="confirm-icon">!</div>
            <p className="eyebrow">REMOVE COMPLETED TASK</p>
            <h2 id="remove-task-title">Remove this task?</h2>
            <p className="muted">
              <strong>{taskToRemove.title}</strong> will be removed from your workspace. This action cannot be undone.
            </p>
            <div className="confirm-actions">
              <button className="secondary-button" onClick={() => setTaskToRemove(null)}>
                Keep task
              </button>
              <button
                className="delete-button confirm-delete"
                disabled={deletingTaskId === taskToRemove.id}
                onClick={() => deleteTask(taskToRemove)}
              >
                {deletingTaskId === taskToRemove.id ? "Removing..." : "Yes, remove it"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.error || "The server request failed.";
  }
  return "Something went wrong. Please try again.";
}

function getToday() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function isDueSoon(value: string) {
  const dueDate = new Date(value);
  const today = new Date();
  const difference = dueDate.getTime() - today.setHours(0, 0, 0, 0);
  return difference >= 0 && difference <= 1000 * 60 * 60 * 24 * 3;
}

function getDueState(task: Task) {
  if (!task.due_date || task.status === "done") {
    return "current";
  }

  const dueDate = new Date(`${task.due_date.slice(0, 10)}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return dueDate < today ? "overdue" : "current";
}

function getOverdueDays(value: string) {
  const dueDate = new Date(`${value.slice(0, 10)}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(1, Math.floor((today.getTime() - dueDate.getTime()) / (1000 * 60 * 60 * 24)));
}

function getInitials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
