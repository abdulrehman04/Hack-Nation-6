import { initializeApp } from 'firebase/app'
import {
  createUserWithEmailAndPassword,
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth'
import type { FirebaseError } from 'firebase/app'
import type { User } from 'firebase/auth'

const firebaseConfig = {
  apiKey: 'AIzaSyD298bLD4CRa87ghE-XOQFlSlpRKN5EphY',
  authDomain: 'hack-nation-6---realdoor.firebaseapp.com',
  projectId: 'hack-nation-6---realdoor',
  storageBucket: 'hack-nation-6---realdoor.firebasestorage.app',
  messagingSenderId: '660081168271',
  appId: '1:660081168271:web:af8dff456598b9cad305fa',
}

const app = initializeApp(firebaseConfig)
const auth = getAuth(app)

export interface AuthedUser {
  uid: string
  email: string | null
  idToken: string
}

export interface Account {
  uid: string
  email: string | null
}

async function toAuthed(user: User): Promise<AuthedUser> {
  return { uid: user.uid, email: user.email, idToken: await user.getIdToken() }
}

// Create-only: used at save time. Fails if the email is already registered.
export async function signUp(email: string, password: string): Promise<AuthedUser> {
  const cred = await createUserWithEmailAndPassword(auth, email, password)
  return toAuthed(cred.user)
}

// Login-only: used on the landing page.
export async function logIn(email: string, password: string): Promise<AuthedUser> {
  const cred = await signInWithEmailAndPassword(auth, email, password)
  return toAuthed(cred.user)
}

export async function logOut(): Promise<void> {
  await signOut(auth)
}

export function onAuth(callback: (account: Account | null) => void): () => void {
  return onAuthStateChanged(auth, (user) =>
    callback(user ? { uid: user.uid, email: user.email } : null))
}

export async function getIdToken(): Promise<string | null> {
  return auth.currentUser ? auth.currentUser.getIdToken() : null
}

export function authErrorMessage(err: unknown): string {
  const code = (err as FirebaseError)?.code
  switch (code) {
    case 'auth/invalid-email':
      return 'That email address looks invalid.'
    case 'auth/weak-password':
      return 'Password is too weak. Use at least 6 characters.'
    case 'auth/email-already-in-use':
      return 'An account with this email already exists. Please log in instead.'
    case 'auth/user-not-found':
      return 'No account found for that email.'
    case 'auth/wrong-password':
    case 'auth/invalid-credential':
      return 'Wrong email or password.'
    case 'auth/operation-not-allowed':
      return 'Email/password sign-in is not enabled for this project yet.'
    case 'auth/too-many-requests':
      return 'Too many attempts. Please wait a moment and try again.'
    default:
      return err instanceof Error ? err.message : 'Something went wrong. Please try again.'
  }
}
