from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .diffing import ADDITION, REVISION, calculate_points, compare
from .models import ChangeSubmission, Project, ProjectMembership

PW = "Pass!12345"
BASE = "The quick brown fox jumps over the lazy dog today"


def mkuser(name, role="student"):
    return User.objects.create_user(name, f"{name}@x.com", PW, role=role, first_name=name.title(), last_name="T")


class DiffTests(TestCase):
    def test_addition_counts_new_words(self):
        r = compare("one two three", "one two three four five")
        self.assertEqual((r["added"], r["removed"]), (2, 0))

    def test_revision_counts_replaced_words(self):
        r = compare("one two three", "one 2 three")
        self.assertEqual((r["added"], r["removed"]), (1, 1))

    def test_no_change(self):
        r = compare("a b c", "a  b   c")
        self.assertEqual((r["added"], r["removed"]), (0, 0))

    def test_points_rates(self):
        self.assertEqual(calculate_points(ADDITION, 10), Decimal("10"))
        self.assertEqual(calculate_points(REVISION, 5), Decimal("2.5"))
        self.assertEqual(calculate_points(REVISION, 1), Decimal("0.5"))


class Base(TestCase):
    def setUp(self):
        self.lead = mkuser("lead")
        self.mem = mkuser("mem")
        self.other = mkuser("other")
        self.inst = mkuser("inst", "instructor")
        self.adm = mkuser("adm", "admin")
        self.client.login(username="lead", password=PW)
        self.client.post(reverse("projects:create"), {"name": "Paper One", "description": "d", "current_text": BASE})
        self.p = Project.objects.get(name="Paper One")
        self.client.post(reverse("projects:member_add", args=[self.p.pk]), {"username": "mem", "role": "member"})

    def login(self, name):
        self.client.logout()
        self.client.login(username=name, password=PW)

    def submit(self, who, text, tag="addition", project=None):
        self.login(who)
        project = project or self.p
        self.client.post(reverse("projects:change_create", args=[project.pk]), {"proposed_text": text, "tag": tag})
        return ChangeSubmission.objects.filter(project=project, author__username=who).latest("id")

    def review(self, who, change, decision, note=""):
        self.login(who)
        return self.client.post(reverse("projects:change_review", args=[change.pk]), {"decision": decision, "review_note": note})


class ProjectTests(Base):
    def test_creator_becomes_leader_and_data_saved(self):
        m = ProjectMembership.objects.get(project=self.p, user=self.lead)
        self.assertEqual(m.role, "leader")
        self.assertEqual(self.p.created_by, self.lead)

    def test_create_validation(self):
        self.login("lead")
        r = self.client.post(reverse("projects:create"), {"name": "ab", "description": "", "current_text": "too short"})
        self.assertContains(r, "at least 3 characters")
        self.assertContains(r, "at least 5 words")
        self.assertEqual(Project.objects.count(), 1)

    def test_only_students_can_create(self):
        for name in ("inst", "adm"):
            self.login(name)
            self.assertEqual(self.client.get(reverse("projects:create")).status_code, 403)

    def test_logged_out_redirected(self):
        self.client.logout()
        for url in (reverse("projects:list"), reverse("projects:detail", args=[self.p.pk]), reverse("projects:create")):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login/", r.url)

    def test_non_member_cannot_view_but_instructor_can(self):
        self.login("other")
        self.assertEqual(self.client.get(reverse("projects:detail", args=[self.p.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse("projects:list")), "Paper One")
        for name in ("inst", "adm"):
            self.login(name)
            self.assertContains(self.client.get(reverse("projects:detail", args=[self.p.pk])), "Read-only")
            self.assertContains(self.client.get(reverse("projects:list")), "Paper One")

    def test_edit_and_delete_leader_only(self):
        self.login("mem")
        self.assertEqual(self.client.get(reverse("projects:edit", args=[self.p.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("projects:delete", args=[self.p.pk])).status_code, 403)
        self.login("lead")
        self.client.post(reverse("projects:edit", args=[self.p.pk]), {"name": "Renamed", "description": ""})
        self.p.refresh_from_db()
        self.assertEqual(self.p.name, "Renamed")
        self.assertEqual(self.p.current_text, BASE)
        self.client.post(reverse("projects:delete", args=[self.p.pk]))
        self.assertFalse(Project.objects.exists())


class MemberTests(Base):
    def test_add_validation(self):
        self.login("lead")
        url = reverse("projects:member_add", args=[self.p.pk])
        for username, msg in (("nobody", "No user named"), ("inst", "Only student"), ("mem", "already in")):
            r = self.client.post(url, {"username": username, "role": "member"}, follow=True)
            self.assertContains(r, msg)

    def test_member_cannot_manage_members(self):
        self.login("mem")
        r = self.client.post(reverse("projects:member_add", args=[self.p.pk]), {"username": "other", "role": "member"})
        self.assertEqual(r.status_code, 403)

    def test_last_leader_protected(self):
        self.login("lead")
        lead_m = ProjectMembership.objects.get(project=self.p, user=self.lead)
        r = self.client.post(reverse("projects:member_role", args=[self.p.pk, lead_m.pk]), follow=True)
        self.assertContains(r, "at least one Leader")
        self.client.post(reverse("projects:member_remove", args=[self.p.pk, lead_m.pk]))
        self.assertTrue(ProjectMembership.objects.filter(pk=lead_m.pk).exists())

    def test_promote_and_remove(self):
        self.login("lead")
        mem_m = ProjectMembership.objects.get(project=self.p, user=self.mem)
        self.client.post(reverse("projects:member_role", args=[self.p.pk, mem_m.pk]))
        mem_m.refresh_from_db()
        self.assertEqual(mem_m.role, "leader")
        self.client.post(reverse("projects:member_remove", args=[self.p.pk, mem_m.pk]))
        self.assertFalse(ProjectMembership.objects.filter(pk=mem_m.pk).exists())

    def test_different_roles_in_different_projects(self):
        self.login("mem")
        self.client.post(reverse("projects:create"), {"name": "Paper Two", "description": "", "current_text": BASE})
        p2 = Project.objects.get(name="Paper Two")
        roles = dict(ProjectMembership.objects.filter(user=self.mem).values_list("project__name", "role"))
        self.assertEqual(roles, {"Paper One": "member", "Paper Two": "leader"})


class ChangeFlowTests(Base):
    def test_full_flow_approve_merges_and_awards_points(self):
        new_text = BASE + " and then it rested quietly"  # 5 added words
        c = self.submit("mem", new_text, "addition")
        self.assertEqual(c.status, "pending")
        self.assertEqual(c.base_text, BASE)
        r = self.review("lead", c, "approve")
        c.refresh_from_db(); self.p.refresh_from_db()
        self.assertEqual(c.status, "approved")
        self.assertEqual(c.points, Decimal("5.0"))
        self.assertEqual(self.p.current_text, new_text)
        self.assertEqual(c.reviewer, self.lead)

    def test_revision_scores_half_point(self):
        c = self.submit("mem", BASE.replace("quick", "speedy").replace("lazy", "sleepy"), "revision")
        self.review("lead", c, "approve")
        c.refresh_from_db()
        self.assertEqual(c.points, Decimal("1.0"))  # 2 replaced words x 0.5

    def test_reject_requires_reason_and_does_not_merge(self):
        c = self.submit("mem", BASE + " extra words here")
        r = self.review("lead", c, "reject", note="", )
        c.refresh_from_db()
        self.assertEqual(c.status, "pending")
        self.review("lead", c, "reject", note="Not relevant")
        c.refresh_from_db(); self.p.refresh_from_db()
        self.assertEqual((c.status, c.points), ("rejected", Decimal("0")))
        self.assertEqual(self.p.current_text, BASE)

    def test_cannot_review_own_change_or_as_member(self):
        c = self.submit("lead", BASE + " leader adds words")
        self.assertEqual(self.review("lead", c, "approve").status_code, 403)
        c2 = self.submit("mem", BASE + " member adds words")
        self.assertEqual(self.review("mem", c2, "approve").status_code, 403)
        self.assertEqual(self.review("inst", c2, "approve").status_code, 403)

    def test_peer_leader_can_review_a_leaders_change(self):
        self.login("lead")
        mem_m = ProjectMembership.objects.get(project=self.p, user=self.mem)
        self.client.post(reverse("projects:member_role", args=[self.p.pk, mem_m.pk]))
        c = self.submit("lead", BASE + " leader adds words")
        self.review("mem", c, "approve")
        c.refresh_from_db()
        self.assertEqual(c.status, "approved")

    def test_validation_no_change_and_missing_tag(self):
        self.login("mem")
        url = reverse("projects:change_create", args=[self.p.pk])
        r = self.client.post(url, {"proposed_text": BASE, "tag": "addition"})
        self.assertContains(r, "No changes detected")
        r = self.client.post(url, {"proposed_text": BASE + " more", "tag": ""})
        self.assertContains(r, "required")
        self.assertFalse(ChangeSubmission.objects.exists())

    def test_non_member_and_instructor_cannot_submit(self):
        for name in ("other", "inst", "adm"):
            self.login(name)
            r = self.client.post(reverse("projects:change_create", args=[self.p.pk]), {"proposed_text": BASE + " x", "tag": "addition"})
            self.assertEqual(r.status_code, 403, name)

    def test_stale_change_cannot_merge_and_edit_starts_from_latest(self):
        a = self.submit("mem", BASE + " alpha beta")
        b = self.submit("lead", BASE + " gamma delta")  # lead's change; mem reviews after promotion
        self.review("lead", a, "approve")
        self.login("lead")
        mem_m = ProjectMembership.objects.get(project=self.p, user=self.mem)
        self.client.post(reverse("projects:member_role", args=[self.p.pk, mem_m.pk]))
        r = self.review("mem", b, "approve")
        b.refresh_from_db()
        self.assertEqual(b.status, "pending")
        self.assertTrue(b.is_stale)
        self.login("lead")
        page = self.client.get(reverse("projects:change_edit", args=[b.pk]))
        self.assertContains(page, "latest official text")
        self.assertContains(page, "alpha beta")

    def test_author_edit_delete_only_while_pending(self):
        c = self.submit("mem", BASE + " one more")
        self.login("lead")
        self.assertEqual(self.client.get(reverse("projects:change_edit", args=[c.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("projects:change_delete", args=[c.pk])).status_code, 403)
        self.login("mem")
        self.client.post(reverse("projects:change_edit", args=[c.pk]), {"proposed_text": BASE + " one more two", "tag": "addition"})
        c.refresh_from_db()
        self.assertTrue(c.proposed_text.endswith("two"))
        self.review("lead", c, "approve")
        self.login("mem")
        self.assertEqual(self.client.post(reverse("projects:change_delete", args=[c.pk])).status_code, 403)

    def test_author_can_delete_pending(self):
        c = self.submit("mem", BASE + " temp words")
        self.login("mem")
        self.client.post(reverse("projects:change_delete", args=[c.pk]))
        self.assertFalse(ChangeSubmission.objects.filter(pk=c.pk).exists())

    def test_change_visibility(self):
        c = self.submit("mem", BASE + " visible words")
        self.login("other")
        self.assertEqual(self.client.get(reverse("projects:change_detail", args=[c.pk])).status_code, 403)
        self.login("inst")
        self.assertEqual(self.client.get(reverse("projects:change_detail", args=[c.pk])).status_code, 200)


class PerProjectPointsTests(Base):
    """Points and leaderboards are per project: top in project 1, low in project 2."""

    def test_points_do_not_mix_between_projects(self):
        self.login("lead")
        self.client.post(reverse("projects:create"), {"name": "Paper Two", "description": "", "current_text": BASE})
        p2 = Project.objects.get(name="Paper Two")
        self.client.post(reverse("projects:member_add", args=[p2.pk]), {"username": "mem", "role": "member"})

        big = self.submit("mem", BASE + " " + " ".join(f"w{i}" for i in range(20)), "addition", self.p)   # 20 pts
        small = self.submit("mem", BASE + " tiny", "addition", p2)                                         # 1 pt
        self.review("lead", big, "approve")
        self.review("lead", small, "approve")

        top1 = self.p.leaderboard()
        top2 = p2.leaderboard()
        self.assertEqual((top1[0]["membership"].user.username, top1[0]["points"]), ("mem", Decimal("20.0")))
        pts2 = {r["membership"].user.username: r["points"] for r in top2}
        self.assertEqual(pts2["mem"], Decimal("1.0"))
        self.assertEqual(pts2["lead"], Decimal("0"))

        self.login("mem")
        dash = self.client.get(reverse("accounts:dashboard_student"))
        self.assertContains(dash, "20.0")
        self.assertContains(dash, "1.0")

    def test_leaderboard_ranks_ties_and_includes_zero(self):
        c = self.submit("mem", BASE + " a b c")
        self.review("lead", c, "approve")
        rows = self.p.leaderboard()
        self.assertEqual([r["rank"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["membership"].user.username, "mem")
        self.assertEqual(rows[1]["points"], Decimal("0"))

    def test_rejected_and_pending_earn_nothing(self):
        c1 = self.submit("mem", BASE + " pending words")
        c2 = self.submit("mem", BASE + " rejected words too")
        self.review("lead", c2, "reject", note="no")
        self.assertEqual(self.p.leaderboard()[0]["points"], Decimal("0"))


class DashboardTests(Base):
    def test_dashboards_render_for_each_role(self):
        c = self.submit("mem", BASE + " dash words")
        for name, text in (("lead", "Changes to review"), ("mem", "My pending"), ("inst", "All projects"), ("adm", "Projects")):
            self.login(name)
            r = self.client.get(reverse("accounts:dashboard"), follow=True)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, text)
        self.login("mem")
        self.assertContains(self.client.get(reverse("projects:my_changes")), "Paper One")
        self.login("inst")
        self.assertEqual(self.client.get(reverse("projects:my_changes")).status_code, 403)
