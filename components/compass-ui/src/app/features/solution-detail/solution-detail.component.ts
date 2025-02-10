import { Component, OnInit, OnDestroy } from "@angular/core";
import { CommonModule, DatePipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { RouterModule, ActivatedRoute } from "@angular/router";
import { HttpClient } from "@angular/common/http";
import { BehaviorSubject, Subject, finalize, takeUntil } from "rxjs";
import { MessageService } from "primeng/api";
import { environment } from "../../../environments/environment";
import { AuthService } from "../../core/services/auth.service";
import { DialogService } from "primeng/dynamicdialog";
import { LoginDialogComponent } from "../../core/components/login-dialog/login-dialog.component";
import { Solution } from "../../shared/interfaces/solution.interface";
import { CommentService, Comment } from "../../core/services/comment.service";
import { RatingService } from "../../core/services/rating.service";
import type { Rating } from "../../core/services/rating.service";

// PrimeNG Components
import { BreadcrumbModule } from "primeng/breadcrumb";
import { ButtonModule } from "primeng/button";
import { CardModule } from "primeng/card";
import { ChipModule } from "primeng/chip";
import { InputTextareaModule } from "primeng/inputtextarea";
import { ProgressSpinnerModule } from "primeng/progressspinner";
import { RatingModule } from "primeng/rating";
import { TabViewModule } from "primeng/tabview";
import { TagModule } from "primeng/tag";
import { ToastModule } from "primeng/toast";

// Markdown
import { MarkdownModule } from "ngx-markdown";

type Severity =
  | "success"
  | "info"
  | "warning"
  | "danger"
  | "secondary"
  | "contrast";

@Component({
  selector: "app-solution-detail",
  templateUrl: "./solution-detail.component.html",
  styleUrls: ["./solution-detail.component.scss"],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    DatePipe,
    BreadcrumbModule,
    ButtonModule,
    CardModule,
    ChipModule,
    InputTextareaModule,
    ProgressSpinnerModule,
    RatingModule,
    TabViewModule,
    TagModule,
    ToastModule,
    MarkdownModule,
  ],
  providers: [DialogService],
})
export class SolutionDetailComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();
  private userCommentsPage = 0;
  private ratingsPage = 0;

  solution$ = new BehaviorSubject<Solution | null>(null);
  officialComments$ = new BehaviorSubject<Comment[]>([]);
  userComments$ = new BehaviorSubject<Comment[]>([]);
  ratings$ = new BehaviorSubject<Rating[]>([]);

  loading = true;
  loadingOfficialComments = false;
  loadingUserComments = false;
  loadingRatings = false;
  hasMoreUserComments = true;
  hasMoreRatings = true;
  totalOfficialComments = 0;
  totalUserComments = 0;
  totalRatings = 0;
  activeTab = 0;
  newComment = "";
  newRating = {
    score: 0,
    comment: "",
  };
  isLoggedIn = false;

  constructor(
    private route: ActivatedRoute,
    private http: HttpClient,
    private messageService: MessageService,
    private authService: AuthService,
    private dialogService: DialogService,
    private commentService: CommentService,
    private ratingService: RatingService
  ) {}

  ngOnInit() {
    this.route.params.pipe(takeUntil(this.destroy$)).subscribe((params) => {
      const slug = params["slug"];
      this.loadSolution(slug);
      this.loadComments(slug);
      this.loadRatings(slug);
    });

    this.authService.currentUser$.subscribe((user) => {
      this.isLoggedIn = !!user;
    });
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  getStageSeverity(stage: string): Severity {
    const severityMap: { [key: string]: Severity } = {
      DEVELOPING: "warning",
      UAT: "info",
      PRODUCTION: "success",
      DEPRECATED: "danger",
      RETIRED: "danger",
    };
    return severityMap[stage] || "info";
  }

  getRecommendStatusSeverity(status: string): Severity {
    const severityMap: { [key: string]: Severity } = {
      ADOPT: "success",
      TRIAL: "info",
      ASSESS: "warning",
      HOLD: "danger",
    };
    return severityMap[status] || "info";
  }

  getAdoptionLevelSeverity(level: string): Severity {
    const severityMap: { [key: string]: Severity } = {
      PILOT: "warning",
      TEAM: "info",
      DEPARTMENT: "success",
      ENTERPRISE: "success",
      INDUSTRY: "success",
    };
    return severityMap[level] || "info";
  }

  private loadSolution(slug: string) {
    this.loading = true;
    this.http
      .get<any>(`${environment.apiUrl}/solutions/${slug}`)
      .pipe(finalize(() => (this.loading = false)))
      .subscribe({
        next: (response) => {
          if (response.success) {
            this.solution$.next(response.data);
          }
        },
        error: (error) => {
          this.messageService.add({
            severity: "error",
            summary: "Error",
            detail: "Failed to load solution details",
          });
        },
      });
  }

  loadComments(slug: string, loadMore = false) {
    if (!loadMore) {
      this.userCommentsPage = 0;
      this.officialComments$.next([]);
      this.userComments$.next([]);
    }

    // Load OFFICIAL comments (max 10)
    this.loadingOfficialComments = true;
    this.commentService
      .getSolutionComments(slug, 0, 10, "OFFICIAL")
      .pipe(
        finalize(() => {
          this.loadingOfficialComments = false;
        }),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (response) => {
          if (response.success) {
            this.officialComments$.next(response.data);
            this.totalOfficialComments = response.total;
          }
        },
        error: (error) => {
          this.messageService.add({
            severity: "error",
            summary: "Error",
            detail: "Failed to load official comments",
          });
        },
      });

    // Load USER comments
    if (!loadMore) {
      this.userCommentsPage = 0;
      this.userComments$.next([]);
    }

    this.loadingUserComments = true;
    this.commentService
      .getSolutionComments(slug, this.userCommentsPage * 10, 10, "USER")
      .pipe(
        finalize(() => {
          this.loadingUserComments = false;
        }),
        takeUntil(this.destroy$)
      )
      .subscribe({
        next: (response) => {
          if (response.success) {
            const currentComments = this.userComments$.value;
            this.userComments$.next([...currentComments, ...response.data]);
            this.totalUserComments = response.total;
            this.hasMoreUserComments = currentComments.length + response.data.length < response.total;
            this.userCommentsPage++;
          }
        },
        error: (error) => {
          this.messageService.add({
            severity: "error",
            summary: "Error",
            detail: "Failed to load user comments",
          });
        },
      });
  }

  loadRatings(slug: string, loadMore = false) {
    if (!loadMore) {
      this.ratingsPage = 0;
      this.ratings$.next([]);
      this.hasMoreRatings = true;
    }

    if (!this.hasMoreRatings || this.loadingRatings) {
      return;
    }

    this.loadingRatings = true;
    const skip = this.ratingsPage * 10;

    this.ratingService
      .getSolutionRatings(slug, skip, 10)
      .pipe(finalize(() => (this.loadingRatings = false)))
      .subscribe({
        next: (response) => {
          if (response.success) {
            const currentRatings = this.ratings$.value;
            this.ratings$.next([...currentRatings, ...response.data]);
            this.totalRatings = response.total;
            this.hasMoreRatings =
              currentRatings.length + response.data.length < response.total;
            this.ratingsPage++;
          }
        },
        error: (error) => {
          this.messageService.add({
            severity: "error",
            summary: "Error",
            detail: "Failed to load ratings",
          });
        },
      });
  }

  submitComment(slug: string) {
    if (!this.newComment.trim()) return;

    this.commentService.addComment(slug, this.newComment).subscribe({
      next: (response) => {
        if (response.success) {
          this.messageService.add({
            severity: "success",
            summary: "Success",
            detail: "Comment added successfully",
          });
          this.newComment = "";
          this.loadComments(slug);
        }
      },
      error: (error) => {
        if (error.status === 401) {
          this.showLoginDialog();
        } else {
          this.messageService.add({
            severity: "error",
            summary: "Error",
            detail: "Failed to add comment",
          });
        }
      },
    });
  }

  submitRating(slug: string) {
    if (!this.isLoggedIn) {
      this.messageService.add({
        severity: "warn",
        summary: "Warning",
        detail: "Please login to submit a rating",
      });
      return;
    }

    if (this.newRating.score === 0) {
      this.messageService.add({
        severity: "warn",
        summary: "Warning",
        detail: "Please select a rating score",
      });
      return;
    }

    this.ratingService
      .addRating(slug, this.newRating.score, this.newRating.comment)
      .subscribe({
        next: (response) => {
          if (response.success) {
            this.messageService.add({
              severity: "success",
              summary: "Success",
              detail: "Rating submitted successfully",
            });
            this.newRating = { score: 0, comment: "" };
            this.loadRatings(slug);
            this.loadSolution(slug);
          }
        },
        error: (error) => {
          this.messageService.add({
            severity: "error",
            summary: "Error",
            detail: error.error?.detail || "Failed to submit rating",
          });
        },
      });
  }

  showLoginDialog() {
    this.dialogService.open(LoginDialogComponent, {
      header: "Login Required",
      width: "400px",
    });
  }
}
