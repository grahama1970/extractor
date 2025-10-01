import Mathlib

theorem sum_of_two_even_numbers (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  rcases ha with ⟨m, hm⟩
  rcases hb with ⟨n, hn⟩
  refine ⟨m + n, ?_⟩
  simp [hm, hn, two_mul, add_comm, add_left_comm, add_assoc]