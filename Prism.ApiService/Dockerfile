FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY Prism.ApiService/Prism.ApiService.csproj Prism.ApiService/
COPY Prism.ServiceDefaults/Prism.ServiceDefaults.csproj Prism.ServiceDefaults/
RUN dotnet restore Prism.ApiService/Prism.ApiService.csproj
COPY Prism.ApiService/ Prism.ApiService/
COPY Prism.ServiceDefaults/ Prism.ServiceDefaults/
RUN dotnet publish Prism.ApiService/Prism.ApiService.csproj -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "Prism.ApiService.dll"]
