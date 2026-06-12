/**
 * Next.js config for the agentINVEST Operator UI v0.1 (thin slice).
 *
 * The console is server-rendered: the pages fetch from the local Restate admin
 * (`:9070`) + ingress (`:8080`) on the SERVER (route handlers / server components),
 * so no Restate URL or any secret reaches the browser. `reactStrictMode` on; no
 * custom server. Dev runs on localhost:4180 (distinct from the agentINVEST TS/Python
 * endpoint ports and those of sibling projects sharing the dev substrate). v0.1
 * posture: NO app-layer auth — single-operator,
 * the network-ACL (Tailscale) is the deploy-step control (a forward item), and the
 * dev UI runs unauthenticated on localhost, correct for the single-operator
 * workstation but NOT a production auth posture.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
