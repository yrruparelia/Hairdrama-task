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
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<"self" | "delegated">("self");
  const [savingTaskId, setSavingTaskId] = useState<string | null>(null);
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
    const storedToken = window.localStorage.getItem("hairdrama_token") || "";
    setToken(storedToken);
    if (!storedToken) {
      setLoading(false);
      return;
    }

    void loadData(storedToken);
  }, []);

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

  function openTaskForm(mode: "self" | "delegated") {
    setFormMode(mode);
    setForm({ title: "", description: "", priority: "medium", due_date: "", assigned_to: "" });
    setShowForm(true);
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
          <span className="count">{boardTasks.length}</span>
        </div>
        <div className="board">
          {board.map((column) => (
            <div className="column" key={column.key}>
              <div className="column-heading">
                <h3>{column.label}</h3>
                <span className="count">{column.tasks.length}</span>
              </div>
              <div className="task-list">
                {column.tasks.length === 0 && <p className="empty">No tasks here yet.</p>}
                {column.tasks.map((task) => (
                  <article className="task-card" key={task.id}>
                    <div className="task-card-top">
                      <span className={`priority ${task.priority}`}>{task.priority}</span>
                      {task.due_date && <time>{task.due_date.slice(0, 10)}</time>}
                    </div>
                    <h3>{task.title}</h3>
                    {task.description && <p>{task.description}</p>}
                    <div className="task-people">
                      <span>Assigner: {task.creator?.name || task.creator?.email || "You"}</span>
                      <span>Doer: {task.assignee?.name || task.assignee?.email || "Unassigned"}</span>
                    </div>
                    <div className="task-card-footer">
                      <span className="assignee">
                        {task.status === "done" ? "Completed" : "In your workspace"}
                      </span>
                      {task.status !== "done" && (
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
        <section className="login-card">
          <div className="brand-mark">H</div>
          <p className="eyebrow">HAIRDRAMA WORKSPACE</p>
          <h1>Make work feel simple.</h1>
          <p className="muted">
            Organize tasks, assign ownership, and keep everyone updated from
            one focused board.
          </p>
          {error && <p className="error">{error}</p>}
          <button className="primary-button wide" onClick={login}>
            Continue with Google
          </button>
          <p className="small-text">
            You will be redirected to Google for secure sign-in.
          </p>
        </section>
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
          <span>{user.name || user.email}</span>
          <button className="text-button" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <section className="content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h1>Task board</h1>
            <p className="muted">Plan clearly. Finish confidently.</p>
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

        <div className="sort-toolbar">
          <label htmlFor="task-sort">Sort tasks</label>
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
