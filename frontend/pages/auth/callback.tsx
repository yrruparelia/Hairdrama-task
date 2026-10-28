import { useEffect, useState } from "react";
import { useRouter } from "next/router";

export default function AuthCallback() {
  const router = useRouter();
  const [message, setMessage] = useState("Completing sign in...");

  useEffect(() => {
    if (!router.isReady) return;
    const token = typeof router.query.token === "string" ? router.query.token : "";
    if (!token) {
      setMessage("No login token was received. Please try again.");
      return;
    }
    window.localStorage.setItem("hairdrama_token", token);
    void router.replace("/");
  }, [router]);

  return <main className="centered">{message}</main>;
}
