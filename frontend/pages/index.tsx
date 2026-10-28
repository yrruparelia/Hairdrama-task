import { FormEvent, useEffect, useMemo, useState } from "react";
import axios from "axios";

type User = {
  id: string;
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
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "medium",
    due_date: "",
    assigned_to: "",
  });

  const groupedTasks = useMemo(
    () =>
      columns.map((column) => ({
        ...column,
        tasks: tasks.filter((task) => task.status === column.key),
      })),
    [tasks],
  );

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
      setUser(meResponse.data);
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
    try {
      const response = await api.post<Task>(
        "/api/tasks/",
        {
          ...form,
          assigned_to: form.assigned_to || null,
          due_date: form.due_date || null,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setTasks((current) => [response.data, ...current]);
      setForm({
        title: "",
        description: "",
        priority: "medium",
        due_date: "",
        assigned_to: "",
      });
      setShowForm(false);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    }
  }

  async function updateStatus(task: Task, status: Task["status"]) {
    setError("");
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
      setError(getErrorMessage(requestError));
    }
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
          <button className="primary-button" onClick={() => setShowForm(true)}>
            + New task
          </button>
        </div>

        {error && <p className="error banner">{error}</p>}

        {showForm && (
          <form className="task-form" onSubmit={createTask}>
            <div className="form-heading">
              <h2>Create a task</h2>
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
                  onChange={(event) =>
                    setForm({ ...form, due_date: event.target.value })
                  }
                />
              </label>
              <label>
                Assign to
                <select
                  value={form.assigned_to}
                  onChange={(event) =>
                    setForm({ ...form, assigned_to: event.target.value })
                  }
                >
                  <option value="">Unassigned</option>
                  {users.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name || item.email}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button className="primary-button" type="submit">
              Create task
            </button>
          </form>
        )}

        <section className="board">
          {groupedTasks.map((column) => (
            <div className="column" key={column.key}>
              <div className="column-heading">
                <h2>{column.label}</h2>
                <span className="count">{column.tasks.length}</span>
              </div>
              <div className="task-list">
                {column.tasks.length === 0 && (
                  <p className="empty">No tasks here yet.</p>
                )}
                {column.tasks.map((task) => (
                  <article className="task-card" key={task.id}>
                    <div className="task-card-top">
                      <span className={`priority ${task.priority}`}>
                        {task.priority}
                      </span>
                      {task.due_date && (
                        <time>{task.due_date.slice(0, 10)}</time>
                      )}
                    </div>
                    <h3>{task.title}</h3>
                    {task.description && <p>{task.description}</p>}
                    <div className="task-card-footer">
                      <span className="assignee">
                        {task.assignee?.name ||
                          task.assignee?.email ||
                          "Unassigned"}
                      </span>
                      {task.status !== "done" && (
                        <button
                          className="complete-button"
                          onClick={() =>
                            updateStatus(
                              task,
                              task.status === "todo" ? "in_progress" : "done",
                            )
                          }
                        >
                          {task.status === "todo" ? "Start" : "Complete"}
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </section>
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
