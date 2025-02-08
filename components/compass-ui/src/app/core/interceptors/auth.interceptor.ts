import { Injectable, Inject } from "@angular/core";
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor,
} from "@angular/common/http";
import { Observable } from "rxjs";
import { environment } from "../../../environments/environment";

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  private apiUrl = environment.apiUrl;
  private tokenKey = "auth_token";

  constructor() {}

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    // Only add token for specific APIs
    if (this.shouldAddToken(request)) {
      const token = this.getAuthToken();
      if (token) {
        request = request.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        });
      }
    }

    return next.handle(request);
  }

  private getAuthToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  private shouldAddToken(request: HttpRequest<unknown>): boolean {
    const url = request.url;
    const method = request.method.toLowerCase();

    // Always add token for /api/users/me and /api/solutions/my/
    if (url === `${this.apiUrl}/users/me` || url.includes("/solutions/my/")) {
      return true;
    }

    // Add token for all POST and PUT requests
    if (
      url.startsWith(this.apiUrl) &&
      (method === "post" || method === "put")
    ) {
      return true;
    }

    return false;
  }
}
