
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyB2o0xsKmyEY1_nmLvW6HH1Ivb26zVLzwE",
  authDomain: "medintro-mcq.firebaseapp.com",
  projectId: "medintro-mcq",
  appId: "1:949981883734:web:b9a432b992b9847b1a3af7"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const db = getFirestore(app);
