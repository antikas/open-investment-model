import { redirect } from 'next/navigation';

/** The console opens on the load-bearing surface — the Approvals queue. */
export default function Home() {
  redirect('/approvals');
}
