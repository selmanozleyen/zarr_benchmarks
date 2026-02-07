plugins {
    java
    application
    id("com.gradleup.shadow") version "9.3.1"
}

java {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

repositories {
    mavenLocal()
    mavenCentral()
    maven {
        url = uri("https://artifacts.unidata.ucar.edu/repository/unidata-all/")
    }
}

dependencies {
    implementation("dev.zarr:zarr-java:0.0.10")
}

application {
    mainClass.set("benchmark.ZarrBenchmarkRead")
}

tasks.withType<com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar> {
    archiveBaseName.set("zarr-java-benchmark")
    archiveClassifier.set("all")
    archiveVersion.set("")
    mergeServiceFiles()
}

// Register additional entry points as separate shadow jar tasks
tasks.register<com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar>("shadowJarRoundtrip") {
    archiveBaseName.set("zarr-java-benchmark-roundtrip")
    archiveClassifier.set("all")
    archiveVersion.set("")
    from(sourceSets.main.get().output)
    configurations = listOf(project.configurations.runtimeClasspath.get())
    mergeServiceFiles()
    manifest {
        attributes["Main-Class"] = "benchmark.ZarrBenchmarkRoundtrip"
    }
}
